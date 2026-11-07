"""Epic (SMART on FHIR) settings, endpoint discovery and the shared HTTP client.

Everything is read from the environment at call time so a missing value shows up
as a clear 503 on /epic/* instead of a crash at import.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger("cloudcare.epic")

SANDBOX_R4_BASE = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
DEFAULT_REDIRECT_URI = "http://localhost:3000/api/auth/callback/epic"

# The five read APIs the app registration selects, as SMART v1 patient scopes.
# openid + fhirUser give us an id_token naming the signed-in MyChart user.
# offline_access is not requested by default: Epic only issues refresh tokens to
# confidential clients that are set up for them (see docs/epic-mychart.md).
DEFAULT_SCOPES = " ".join(
    [
        "openid",
        "fhirUser",
        "patient/MedicationRequest.read",
        "patient/Medication.read",
        "patient/Observation.read",
        "patient/Encounter.read",
        "patient/DocumentReference.read",
    ]
)

HTTP_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
DISCOVERY_TTL_SECONDS = 3600


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _truthy(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class EpicSettings:
    client_id: str
    client_secret: str
    fhir_base_url: str
    stu3_base_url: str
    redirect_uri: str
    scopes: str
    encryption_key: str
    sandbox: bool
    labs_fhir_version: str  # "STU3" (Epic's labs API) or "R4"

    @property
    def missing(self) -> list[str]:
        """Env vars that must be set before the MyChart connection can work."""
        out = []
        if not self.client_id:
            out.append("EPIC_CLIENT_ID")
        if not self.encryption_key:
            out.append("EPIC_TOKEN_ENCRYPTION_KEY")
        return out

    @property
    def configured(self) -> bool:
        return not self.missing

    @property
    def confidential(self) -> bool:
        return bool(self.client_secret)


def normalize_base(url: str) -> str:
    return url.strip().rstrip("/")


def get_settings() -> EpicSettings:
    fhir_base = normalize_base(_env("EPIC_FHIR_BASE_URL", SANDBOX_R4_BASE))
    default_stu3 = fhir_base[: -len("/R4")] + "/STU3" if fhir_base.upper().endswith("/R4") else fhir_base
    labs_version = _env("EPIC_LABS_FHIR_VERSION", "STU3").upper()
    return EpicSettings(
        client_id=_env("EPIC_CLIENT_ID"),
        client_secret=_env("EPIC_CLIENT_SECRET"),
        fhir_base_url=fhir_base,
        stu3_base_url=normalize_base(_env("EPIC_STU3_BASE_URL", default_stu3)),
        redirect_uri=_env("EPIC_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        scopes=" ".join(_env("EPIC_SCOPES", DEFAULT_SCOPES).split()),
        encryption_key=_env("EPIC_TOKEN_ENCRYPTION_KEY"),
        sandbox=_truthy(_env("EPIC_SANDBOX", "true")),
        labs_fhir_version=labs_version if labs_version in ("STU3", "R4") else "STU3",
    )


# ---- HTTP client -----------------------------------------------------------------
# Tests swap in an httpx.MockTransport here so nothing ever reaches Epic.

_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport
    clear_discovery_cache()


def http_client() -> httpx.Client:
    return httpx.Client(timeout=HTTP_TIMEOUT, transport=_transport, follow_redirects=False)


# ---- SMART discovery ---------------------------------------------------------------


class EpicUnavailable(Exception):
    """Epic could not be reached or answered with something unusable."""


@dataclass(frozen=True)
class SmartEndpoints:
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str | None


_discovery_cache: dict[str, tuple[float, SmartEndpoints]] = {}
_discovery_lock = threading.Lock()


def clear_discovery_cache() -> None:
    with _discovery_lock:
        _discovery_cache.clear()


def discover(fhir_base: str) -> SmartEndpoints:
    """Reads <fhir base>/.well-known/smart-configuration, cached for an hour."""
    base = normalize_base(fhir_base)
    now = time.monotonic()
    with _discovery_lock:
        hit = _discovery_cache.get(base)
        if hit and now - hit[0] < DISCOVERY_TTL_SECONDS:
            return hit[1]

    url = f"{base}/.well-known/smart-configuration"
    try:
        with http_client() as client:
            res = client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        log.warning("epic.discovery.network_error type=%s", type(exc).__name__)
        raise EpicUnavailable("Couldn't reach Epic") from exc
    if res.status_code != 200:
        log.warning("epic.discovery.failed status=%s", res.status_code)
        raise EpicUnavailable("Epic's SMART configuration is unavailable")
    try:
        doc = res.json()
        endpoints = SmartEndpoints(
            authorization_endpoint=str(doc["authorization_endpoint"]),
            token_endpoint=str(doc["token_endpoint"]),
            revocation_endpoint=str(doc["revocation_endpoint"]) if doc.get("revocation_endpoint") else None,
        )
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("epic.discovery.malformed")
        raise EpicUnavailable("Epic's SMART configuration is malformed") from exc
    for endpoint in (endpoints.authorization_endpoint, endpoints.token_endpoint):
        if not endpoint.startswith("https://"):
            raise EpicUnavailable("Epic's SMART configuration lists a non-HTTPS endpoint")

    with _discovery_lock:
        _discovery_cache[base] = (now, endpoints)
    return endpoints
