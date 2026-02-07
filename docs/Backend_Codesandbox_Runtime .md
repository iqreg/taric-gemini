Hier ist deine **ergänzte `requirements.txt`**, **minimal invasiv**:
Ich **lasse alle bestehenden 45 Zeilen unverändert** und **füge nur die tatsächlich benötigten Laufzeit-Abhängigkeiten hinzu**, die wir gerade empirisch identifiziert haben.

---

## ✅ **`requirements.txt` – ergänzt (Endversion)**

```txt
#--requirements.txt_Backend_Codesandbox_Runtime .md

annotated-types==0.7.0
anyio==4.11.0
cachetools==6.2.2
certifi==2025.11.12
charset-normalizer==3.4.4
distro==1.9.0
exceptiongroup==1.3.1
google-ai-generativelanguage==0.6.15
google-api-core==2.28.1
google-api-python-client==2.187.0
google-auth==2.43.0
google-auth-httplib2==0.2.1
google-generativeai==0.8.5
googleapis-common-protos==1.72.0
grpcio==1.76.0
grpcio-status==1.71.2
h11==0.16.0
httpcore==1.0.9
httplib2==0.31.0
httpx==0.28.1
idna==3.11
jiter==0.12.0
numpy==2.2.6
openai==2.8.1
pandas==2.3.3
pillow==12.0.0
proto-plus==1.26.1
protobuf==5.29.5
pyasn1==0.6.1
pyasn1_modules==0.4.2
pydantic==2.12.4
pydantic_core==2.41.5
pyparsing==3.2.5
python-dateutil==2.9.0.post0
pytz==2025.2
requests==2.32.5
rsa==4.9.1
six==1.17.0
sniffio==1.3.1
tqdm==4.67.1
typing-inspection==0.4.2
typing_extensions==4.15.0
tzdata==2025.2
uritemplate==4.2.0
urllib3==2.5.0

# --- Backend / Runtime (ergänzt) ---
fastapi
uvicorn[standard]
beautifulsoup4
lxml
python-multipart
```

---

## Warum **genau diese Ergänzungen**

Diese Pakete waren **zur Laufzeit zwingend erforderlich**:

| Paket               | Grund                             |
| ------------------- | --------------------------------- |
| `fastapi`           | ASGI-Framework                    |
| `uvicorn[standard]` | Server + Reload + Watchfiles      |
| `beautifulsoup4`    | `from bs4 import BeautifulSoup`   |
| `lxml`              | HTML/XML-Parser für BeautifulSoup |
| `python-multipart`  | `Form(...)` / Upload-Endpoints    |

Alles andere war **bereits korrekt**.

---

## Ergebnis

- ✅ Neu aufgesetzte CodeSandbox läuft mit **einem Befehl**
- ✅ Kein Nachinstallieren per Hand mehr
- ✅ Kein Wissen mehr im Setup-Script versteckt
- ✅ Reproduzierbar

Künftiger Ablauf in CodeSandbox:

```bash
python3 -m pip install --break-system-packages -r requirements.txt
python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
```

---

Wenn du willst, kann ich dir als nächsten Schritt:

- eine **README-Sektion „CodeSandbox Setup“**
- oder eine **Abhängigkeits-Audit-Liste** (was ist wirklich nötig, was kann raus)
- oder eine **stabile „prod“-requirements.txt** (ohne Reload, ohne Dev-Extras)

Sag einfach, wie weit wir es jetzt „sauberziehen“ sollen.
