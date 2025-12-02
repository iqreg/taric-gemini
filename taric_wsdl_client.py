"""
taric_wsdl_client.py

Verantwortung:
- Kommunikation mit der TARIC WSDL-API der EU-Kommission
- SOAP-Request bauen
- SOAP/XML-Response parsen
- Ergebnis als neutrales Python-Dict zurückgeben

WICHTIG:
- Die echte Endpoint-URL und die SOAP-Action müssen aus der offiziellen
  Dokumentation / WSDL gezogen und hier eingetragen werden.
"""

from typing import Optional, Dict
import os
import logging
import datetime

import requests  # ggf. in requirements aufnehmen

logger = logging.getLogger(__name__)

# Platzhalter – hier später die echte WSDL/SOAP-Endpoint-URL hinterlegen
TARIC_WSDL_ENDPOINT = os.getenv(
    "TARIC_WSDL_ENDPOINT",
    "https://ec.europa.eu/taxation_customs/dds2/taric/services/goods"  # Beispiel / TODO
)


class TaricWsdlError(Exception):
    """Allgemeiner Fehler beim TARIC-WSDL-Aufruf."""


def fetch_from_wsdl(taric_code: str, lang: str = "DE") -> Optional[Dict]:
    """
    Ruft die offizielle TARIC-Beschreibung für einen TARIC-Code via WSDL/SOAP ab.

    :param taric_code: TARIC / Goods Code, vorzugsweise 10-stellig (z.B. '8517120000').
    :param lang: Sprachcode, z.B. 'DE', 'EN'.
    :return: Dict mit Beschreibung oder None bei „nicht gefunden“.
    :raises TaricWsdlError: bei technischen Fehlern / Parserfehlern.
    """

    taric_code = (taric_code or "").strip()
    if not taric_code:
        logger.warning("fetch_from_wsdl: leerer TARIC-Code")
        return None

    lang = (lang or "DE").upper()

    # TODO: Hier konkretes SOAP-Envelope laut WSDL einbauen.
    # Aktuell nur ein Dummy-Request-Body als Platzhalter.
    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tar="http://example.org/taric">
  <soapenv:Header/>
  <soapenv:Body>
    <tar:getGoodsDescription>
      <tar:code>{taric_code}</tar:code>
      <tar:language>{lang}</tar:language>
    </tar:getGoodsDescription>
  </soapenv:Body>
</soapenv:Envelope>
"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        # "SOAPAction": "..."  # TODO: SOAPAction aus WSDL eintragen, falls erforderlich
    }

    logger.info("TARIC WSDL Request: code=%s, lang=%s", taric_code, lang)

    try:
        resp = requests.post(TARIC_WSDL_ENDPOINT, data=soap_body.encode("utf-8"), headers=headers, timeout=15)
    except Exception as exc:
        logger.exception("Fehler beim HTTP-Request an TARIC-WSDL")
        raise TaricWsdlError(f"HTTP-Fehler beim TARIC-WSDL-Aufruf: {exc}") from exc

    if resp.status_code != 200:
        logger.error("TARIC-WSDL HTTP-Status != 200: %s", resp.status_code)
        raise TaricWsdlError(f"Unerwarteter HTTP-Status {resp.status_code} von TARIC-WSDL")

    raw_xml = resp.text

    # TODO: Hier XML mit z.B. `xml.etree.ElementTree` oder `lxml` parsen
    # und die tatsächliche Description extrahieren.
    #
    # Aktuell nur Dummy-Wert als Platzhalter:

    description = f"[OFFIZIELLE TARIC-Beschreibung für {taric_code} – TODO: XML-Parsing implementieren]"

    result = {
        "taric_code": taric_code,
        "language": lang,
        "description": description,
        "source": "EU_TARIC_WSDL",
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
        "raw": raw_xml,
    }

    return result
