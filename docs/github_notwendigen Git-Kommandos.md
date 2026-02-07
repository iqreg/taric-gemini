Hier sind **nur die notwendigen Git-Kommandos**, **in der richtigen Reihenfolge**, jeweils **kurz erklärt**.
Ausgehend davon, dass du **auf `codesandbox`** bist und **README + requirements.txt** geändert wurden.

---

## 1️⃣ Aktuellen Status prüfen

```bash
git status
```

**Warum:**
Zeigt dir exakt, **welche Dateien geändert** wurden (z. B. `README.md`, `requirements.txt`).

---

## 2️⃣ Änderungen zum Commit vormerken (stagen)

```bash
git add README.md requirements.txt
```

**Warum:**
Nur diese beiden Dateien werden in den Commit aufgenommen – nichts anderes.

_(Alternativ, wenn du sicher bist, dass nur diese zwei geändert wurden)_

```bash
git add .
```

---

## 3️⃣ Commit erstellen

```bash
git commit -m "docs: add complete CodeSandbox setup README and finalize runtime dependencies"
```

**Warum:**

- `docs:` → klare Konvention
- Commit beschreibt **genau**, was gesichert wird
- sauber nachvollziehbar in der Historie

---

## 4️⃣ Auf GitHub pushen (Branch `codesandbox`)

```bash
git push origin codesandbox
```

**Warum:**

- sichert **genau diese funktionierende Version** auf GitHub
- kein Einfluss auf `main`
- jederzeit reproduzierbar

---

## 5️⃣ Kontrolle (optional, aber empfohlen)

```bash
git log --oneline -3
```

**Warum:**
Bestätigt, dass dein Commit jetzt **oben in der History** liegt.

---

## Ergebnis

- ✅ Funktionierende Version ist **dauerhaft gesichert**
- ✅ README dokumentiert den realen Betrieb
- ✅ `codesandbox` bleibt klar getrennt von `main`
- ✅ Saubere Basis für Weiterentwicklung

---

## git add

`git add`
hat mehrere **Argumente/Optionen**, mit denen du **präzise steuerst**, _was_ in den nächsten Commit aufgenommen wird.
Hier ist eine **übersichtliche, praxisnahe Referenz**, von **einfach** bis **fortgeschritten**.

---

## Grundform

```bash
git add <pfad>
```

Beispiele:

```bash
git add README.md
git add requirements.txt
git add src/
```

---

## Häufige Argumente (die du wirklich brauchst)

### `git add .`

```bash
git add .
```

- Fügt **alle neuen und geänderten Dateien** im aktuellen Verzeichnis hinzu
- **Ignoriert gelöschte Dateien**
- Am häufigsten verwendet

---

### `git add -A` (oder `--all`)

```bash
git add -A
```

- Fügt **alles** hinzu:

  - neue Dateien
  - geänderte Dateien
  - **gelöschte Dateien**

- Entspricht: _„Arbeitsverzeichnis = nächster Commit“_
- **Empfohlen für saubere Commits**

---

### `git add -u` (oder `--update`)

```bash
git add -u
```

- Fügt **nur Änderungen an bereits getrackten Dateien** hinzu
- **Keine neuen Dateien**
- Gut, wenn neue Dateien bewusst ausgeschlossen werden sollen

---

### `git add <datei1> <datei2>`

```bash
git add README.md requirements.txt
```

- Sehr **präzise**
- Ideal für **kontrollierte Commits**

---

## Interaktiv / Fortgeschritten

### `git add -p` (Patch-Modus)

```bash
git add -p
```

- Geht **Hunk für Hunk** durch Änderungen
- Du entscheidest pro Codeblock:

  - hinzufügen / überspringen

- Perfekt für:

  - saubere Commits
  - Refactoring + Feature trennen

---

### `git add -i` (Interaktiv)

```bash
git add -i
```

- Menübasierte Oberfläche
- Stagen / Unstagen / Patch / Diff
- Gut, wenn du Git besser verstehen willst

---

## Nützliche Sonderfälle

### Nur Löschungen stagen

```bash
git add -u
```

### Alles zurücknehmen (unstage)

```bash
git reset
```

### Datei aus dem Index entfernen, aber lokal behalten

```bash
git rm --cached <datei>
```

---

## Typische Fehler & Tipps

### ❌ „Zu viel gestaged“

```bash
git reset HEAD <datei>
```

### ✔ Vor dem Commit immer prüfen

```bash
git status
```

---

## Empfehlung für deinen Fall

Für dich (strukturiert, reproduzierbar):

```bash
git add README.md requirements.txt
git commit -m "docs: finalize CodeSandbox setup and dependencies"
```

Oder wenn du sicher bist:

```bash
git add -A
git commit -m "chore: sync working tree"
```

---

## Merksatz

- `git add .` → schnell, aber nicht vollständig
- `git add -A` → vollständig, sauber
- `git add -p` → präzise, professionell

Wenn du willst, erkläre ich dir als Nächstes **git commit** oder **git reset** genauso kompakt.

---

Wenn du willst, gehen wir als Nächstes strukturiert weiter mit:

- Merge-Strategie (`codesandbox` → `main`)
- Tag/Release (`vX.Y-codesandbox`)
- oder technischer Aufräumrunde (Dependencies, Architektur)
