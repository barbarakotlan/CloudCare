"""Reads a connected patient's records from Epic's FHIR API.

- Bearer GETs with Accept: application/fhir+json.
- Paging follows Bundle.link[rel=next], but only to URLs under the FHIR base we
  were configured with, so the token is never sent anywhere else.
- 401: one refresh attempt (when we hold a refresh token), then the connection is
  marked revoked. 403/404 (and other errors) on one resource never fail the whole
  request: that resource comes back empty and is listed in `missing`.

Logs carry event names and status codes only.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit

import httpx

from app.epic import normalize
from app.epic.config import EpicSettings, EpicUnavailable, discover, http_client
from app.epic.oauth import EpicOAuthError, TokenSet, as_utc, refresh_tokens, utcnow

log = logging.getLogger("cloudcare.epic")

FHIR_JSON = "application/fhir+json"
MAX_PAGES = 5
MAX_NOTE_BODIES = 10
MAX_NOTE_BYTES = 256 * 1024
TEXT_TYPES = ("text/plain", "text/html")


class EpicRevoked(Exception):
    """Epic no longer accepts this connection's tokens."""


class ResourceMissing(Exception):
    def __init__(self, reason: str, status_code: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def _reason_for(status_code: int) -> str:
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    return "unavailable"


@dataclass
class EpicFhirClient:
    """Holds the decrypted tokens for one request and talks to Epic.

    `on_tokens` persists refreshed tokens; `refresh_token` is None for public
    clients (Epic gives those no refresh token).
    """

    settings: EpicSettings
    patient_id: str
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None = None
    on_tokens: Callable[[TokenSet], None] | None = None
    http: httpx.Client = field(default_factory=http_client)
    _refreshed: bool = False

    def close(self) -> None:
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- tokens -----------------------------------------------------------------

    def ensure_fresh(self) -> None:
        """Refreshes ahead of time when the access token is (nearly) expired."""
        expires_at = as_utc(self.expires_at)
        if expires_at is None or expires_at - timedelta(seconds=60) > utcnow():
            return
        if not self.refresh_token:
            # Public client: the token simply ran out. Same outcome as a revoke.
            log.info("epic.token.expired_no_refresh")
            raise EpicRevoked()
        self._refresh()

    def _refresh(self) -> None:
        if not self.refresh_token or self._refreshed:
            raise EpicRevoked()
        self._refreshed = True
        try:
            endpoints = discover(self.settings.fhir_base_url)
            tokens = refresh_tokens(endpoints.token_endpoint, self.settings, self.refresh_token)
        except EpicOAuthError:
            raise EpicRevoked()
        self.access_token = tokens.access_token
        if tokens.refresh_token:
            self.refresh_token = tokens.refresh_token
        self.expires_at = tokens.expires_at
        if self.on_tokens:
            self.on_tokens(tokens)

    # ---- HTTP -------------------------------------------------------------------

    def _allowed(self, url: str) -> bool:
        target = urlsplit(url)
        for base in (self.settings.fhir_base_url, self.settings.stu3_base_url):
            b = urlsplit(base)
            same_origin = target.scheme == b.scheme and target.netloc == b.netloc
            if same_origin and (target.path == b.path or target.path.startswith(b.path.rstrip("/") + "/")):
                return True
        return False

    def get(self, url: str, params: dict | None = None, *, accept: str = FHIR_JSON, revocable: bool = True) -> httpx.Response:
        """GET with the bearer token. Raises EpicRevoked or ResourceMissing."""
        if not self._allowed(url):
            log.warning("epic.fhir.blocked_url")
            raise ResourceMissing("blocked")

        for attempt in (1, 2):
            try:
                res = self.http.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {self.access_token}", "Accept": accept},
                )
            except httpx.HTTPError as exc:
                log.warning("epic.fhir.network_error type=%s", type(exc).__name__)
                raise ResourceMissing("unreachable")
            if res.status_code == 401 and attempt == 1 and revocable:
                if not self.refresh_token:
                    log.info("epic.fhir.unauthorized_no_refresh")
                    raise EpicRevoked()
                log.info("epic.fhir.unauthorized_refreshing")
                self._refresh()
                continue
            if res.status_code == 401 and revocable:
                log.info("epic.fhir.unauthorized_after_refresh")
                raise EpicRevoked()
            if res.status_code != 200:
                raise ResourceMissing(_reason_for(res.status_code), res.status_code)
            return res
        raise EpicRevoked()  # pragma: no cover

    def search(self, base: str, resource_type: str, params: dict, *, revocable: bool = True) -> list[dict]:
        """All matching resources across pages (up to MAX_PAGES)."""
        url: str | None = f"{base}/{resource_type}"
        query: dict | None = params
        out: list[dict] = []
        for _ in range(MAX_PAGES):
            if url is None:
                break
            res = self.get(url, query, revocable=revocable)
            try:
                bundle = res.json()
            except ValueError:
                raise ResourceMissing("malformed")
            if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
                raise ResourceMissing("malformed")
            for entry in bundle.get("entry") or []:
                resource = entry.get("resource") if isinstance(entry, dict) else None
                # Epic adds OperationOutcome entries (search.mode = outcome) for warnings.
                if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
                    out.append(resource)
            url = _next_link(bundle)
            query = None
            if url is not None and not self._allowed(url):
                log.warning("epic.fhir.next_link_off_base; stopping pagination")
                break
        return out

    def read(self, base: str, resource_type: str, resource_id: str) -> dict | None:
        try:
            res = self.get(f"{base}/{resource_type}/{resource_id}")
            data = res.json()
        except (ResourceMissing, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("resourceType") == resource_type else None


def _next_link(bundle: dict) -> str | None:
    for link in bundle.get("link") or []:
        if isinstance(link, dict) and link.get("relation") == "next" and isinstance(link.get("url"), str):
            return link["url"]
    return None


# ---- record fetchers ---------------------------------------------------------------------


def _medications(client: EpicFhirClient) -> list[dict]:
    base = client.settings.fhir_base_url
    requests = client.search(base, "MedicationRequest", {"patient": client.patient_id})
    cache: dict[str, dict | None] = {}

    def resolve(reference: str) -> dict | None:
        # "Medication/abc" (relative) or an absolute URL under our base.
        ref = reference.split("/_history/")[0]
        parts = ref.rstrip("/").split("/")
        if len(parts) < 2 or parts[-2] != "Medication":
            return None
        med_id = parts[-1]
        if med_id not in cache:
            cache[med_id] = client.read(base, "Medication", med_id) if normalize.is_fhir_id(med_id) else None
        return cache[med_id]

    return [normalize.medication(r, resolve) for r in requests]


def _labs(client: EpicFhirClient) -> list[dict]:
    params = {"patient": client.patient_id, "category": "laboratory"}
    if client.settings.labs_fhir_version == "STU3":
        try:
            # STU3 is a different FHIR endpoint; a 401 there can mean "this token
            # isn't valid for STU3", not "revoked", so it doesn't trigger the revoke path.
            resources = client.search(client.settings.stu3_base_url, "Observation", params, revocable=False)
            return [normalize.lab(r) for r in resources]
        except ResourceMissing as exc:
            log.info("epic.fhir.labs_stu3_missing reason=%s; trying R4", exc.reason)
    resources = client.search(client.settings.fhir_base_url, "Observation", params)
    return [normalize.lab(r) for r in resources]


def _encounters(client: EpicFhirClient) -> list[dict]:
    resources = client.search(client.settings.fhir_base_url, "Encounter", {"patient": client.patient_id})
    return [normalize.encounter(r) for r in resources]


def _note_text(client: EpicFhirClient, doc: dict) -> str | None:
    """Plain text of a note when it is small text/html or text/plain; else None."""
    for content in doc.get("content") or []:
        attachment = content.get("attachment") if isinstance(content, dict) else None
        if not isinstance(attachment, dict):
            continue
        content_type = str(attachment.get("contentType") or "").split(";")[0].strip().lower()
        if content_type not in TEXT_TYPES:
            continue
        size = attachment.get("size")
        if isinstance(size, int) and size > MAX_NOTE_BYTES:
            continue
        if attachment.get("data"):
            raw = normalize.decode_base64(attachment["data"])
        elif isinstance(attachment.get("url"), str):
            url = urljoin(client.settings.fhir_base_url + "/", attachment["url"])
            try:
                res = client.get(url, accept=content_type)
            except ResourceMissing:
                continue
            if len(res.content) > MAX_NOTE_BYTES:
                continue
            raw = res.text
            # Some servers ignore Accept and wrap the content in a Binary resource.
            if res.headers.get("content-type", "").startswith(("application/fhir+json", "application/json")):
                try:
                    binary = res.json()
                    raw = normalize.decode_base64(binary.get("data") or "")
                except ValueError:
                    raw = None
        else:
            raw = None
        if raw:
            return normalize.note_plain_text(raw, content_type)
    return None


def _notes(client: EpicFhirClient) -> list[dict]:
    docs = client.search(
        client.settings.fhir_base_url,
        "DocumentReference",
        {"patient": client.patient_id, "category": "clinical-note"},
    )
    docs.sort(key=normalize.note_sort_key, reverse=True)
    out = []
    for index, doc in enumerate(docs):
        text = _note_text(client, doc) if index < MAX_NOTE_BODIES else None
        out.append(normalize.note(doc, text))
    return out


FETCHERS: list[tuple[str, Callable[[EpicFhirClient], list[dict]]]] = [
    ("medications", _medications),
    ("encounters", _encounters),
    ("labs", _labs),
    ("notes", _notes),
]


def fetch_records(client: EpicFhirClient) -> dict:
    """{medications, labs, encounters, notes, missing, missing_reasons}. Raises EpicRevoked."""
    client.ensure_fresh()
    out: dict = {"missing": [], "missing_reasons": {}}
    for key, fetcher in FETCHERS:
        try:
            out[key] = fetcher(client)
            log.info("epic.fhir.fetched resource=%s count=%d", key, len(out[key]))
        except ResourceMissing as exc:
            out[key] = []
            out["missing"].append(key)
            out["missing_reasons"][key] = exc.reason
            log.info("epic.fhir.missing resource=%s reason=%s status=%s", key, exc.reason, exc.status_code)
    for key in ("medications", "labs", "encounters", "notes"):
        out[key] = normalize.sort_newest_first(key, out[key])
    if len(out["missing"]) == len(FETCHERS) and all(r == "unreachable" for r in out["missing_reasons"].values()):
        raise EpicUnavailable("Couldn't reach Epic")
    return out
