from collections import defaultdict
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup
import json
import requests
import streamlit as st

st.title("📅 Il mio Orario - Sapienza")

# --- BARRA LATERALE PER I PARAMETRI ---
st.sidebar.header("⚙️ Configurazione")

# 1. Input per cambiare il codice del corso
codice_corso = st.sidebar.text_input("Codice Corso di Laurea", value="33503")

# 2. Input per selezionare l'arco temporale
st.sidebar.subheader("Arco Temporale")
data_inizio_default = date(2026, 10, 12)
data_fine_default = date(2026, 10, 19)

data_inizio = st.sidebar.date_input("Data Inizio", value=data_inizio_default)
data_fine = st.sidebar.date_input("Data Fine", value=data_fine_default)

# Formattazione delle date nel formato ISO richiesto dall'API
start_str = f"{data_inizio.isoformat()}T00:00:00.000Z"
end_str = f"{data_fine.isoformat()}T00:00:00.000Z"

# Richiesta dinamica basata sui controlli della sidebar
url_api = (
    f"https://corsidilaurea.uniroma1.it/it/services/gomp/timetable-data/{codice_corso}"
)

try:
  response = requests.get(
      url=url_api, params={"start": start_str, "end": end_str}, timeout=30
  )
  data = response.json()
except Exception as e:
  st.error(f"Errore nella richiesta API: {e}")
  data = {"events": []}

# Salvataggio e lettura file (come nel tuo codice)
with open("data.json", "w", encoding="utf-8") as f:
  json.dump(data, f, indent=4)

with open("data.json", "r", encoding="utf-8") as f:
  data = json.load(f)


def title(i):
  g = BeautifulSoup(i["title"], "html.parser")

  # Estrazione docente e link ufficiale
  teacher_tag = g.select_one("p.cal-teacher a")
  if teacher_tag:
    teacher = teacher_tag.get_text()
    teacher_href = teacher_tag.get("href", "")
    if teacher_href.startswith("/"):
      teacher_url = f"https://corsidilaurea.uniroma1.it{teacher_href}"
    elif teacher_href:
      teacher_url = teacher_href
    else:
      teacher_url = (
          f"https://www.google.com/search?q=Sapienza+docente+{teacher}"
      )
  else:
    teacher = "Docente non specificato"
    teacher_url = "#"

  # Estrazione aula e generazione link di ricerca mirata su Google Maps
  room_tag = g.select_one("p.cal-space")
  room = room_tag.get_text() if room_tag else "Aula non specificata"
  # URL ottimizzato per Google Maps con il nome completo dell'ateneo e dell'aula
  room_url = f"https://www.google.com/maps/search/?api=1&query=Sapienza+Universita+di+Roma+{room}"

  materia_tag = g.select_one("b")
  materia = materia_tag.get_text() if materia_tag else "Materia"

  return materia, teacher, teacher_url, room, room_url


lezioni = []

for i in data.get("events", []):
  materia, docente, docente_url, aula, aula_url = title(i)
  lezioni.append({
      "materia": materia,
      "docente": docente,
      "docente_url": docente_url,
      "aula": aula,
      "aula_url": aula_url,
      "inizio": i["start"],
      "fine": i["end"],
      "anni": i["course_years"],
      "canali": i["partitions"],
  })

# --- ESTRAZIONE DINAMICA DI ANNI E CANALI (SENZA DUPLICATI) ---
tutti_gli_anni = sorted(
    list(
        set(
            str(anno)
            for l in lezioni
            for anno in l["anni"]
            if anno is not None
        )
    )
)

tutti_i_canali = sorted(
    list(
        set(
            str(canale).strip()
            for l in lezioni
            for canale in l["canali"]
            if canale is not None and str(canale).strip() != ""
        )
    )
)

# --- BARRA LATERALE: FILTRI ---
st.sidebar.divider()
st.sidebar.header("🔍 Filtri")

ricerca = st.sidebar.text_input("Cerca per materia/docente/aula").lower()

filtro_anno = st.sidebar.selectbox(
    "Filtra per Anno", ["Tutti gli anni"] + tutti_gli_anni
)
filtro_canale = st.sidebar.selectbox(
    "Filtra per Canale", ["Tutti i canali"] + tutti_i_canali
)

# --- APPLICAZIONE DEI FILTRI ---
lezioni_filtrate = []
for l in lezioni:
  match_testo = (
      not ricerca
      or ricerca in l["materia"].lower()
      or ricerca in l["docente"].lower()
      or ricerca in l["aula"].lower()
  )

  match_anno = (
      filtro_anno == "Tutti gli anni"
      or int(filtro_anno) in l["anni"]
      or filtro_anno in [str(a) for a in l["anni"]]
  )

  match_canale = (
      filtro_canale == "Tutti i canali"
      or filtro_canale in [str(c) for c in l["canali"]]
  )

  if match_testo and match_anno and match_canale:
    lezioni_filtrate.append(l)

# --- VISUALIZZAZIONE A TABELLE PER GIORNO ---
st.write(
    f"Trovate **{len(lezioni_filtrate)}** lezioni per il corso `{codice_corso}`"
    f" dal {data_inizio} al {data_fine}:"
)
st.divider()

giorni_it = {
    0: "Lunedì",
    1: "Martedì",
    2: "Mercoledì",
    3: "Giovedì",
    4: "Venerdì",
    5: "Sabato",
    6: "Domenica",
}

lezioni_per_giorno = defaultdict(list)
for l in lezioni_filtrate:
  dt = datetime.fromisoformat(l["inizio"].replace("Z", "+00:00"))
  data_formatata = dt.strftime("%d/%m/%Y")
  nome_giorno = giorni_it[dt.weekday()]
  chiave = f"{nome_giorno} ({data_formatata})"
  lezioni_per_giorno[chiave].append(l)

if not lezioni_filtrate:
  st.info("Nessuna lezione trovata con i filtri attuali.")
else:
  for giorno, lista_lezioni in sorted(lezioni_per_giorno.items()):
    st.subheader(f"📅 {giorno}")

    markdown_table = (
        "| Orario | Materia | Docente | Aula | Canali | Anni |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )

    for l in sorted(lista_lezioni, key=lambda x: x["inizio"]):
      ora_inizio = datetime.fromisoformat(
          l["inizio"].replace("Z", "+00:00")
      ).strftime("%H:%M")
      ora_fine = datetime.fromisoformat(
          l["fine"].replace("Z", "+00:00")
      ).strftime("%H:%M")

      # Testo cliccabile pulito tramite Markdown
      docente_link = f"[{l['docente']}]({l['docente_url']})"
      aula_link = f"[{l['aula']}]({l['aula_url']})"

      canali_str = ", ".join(map(str, l["canali"]))
      anni_str = ", ".join(map(str, l["anni"]))

      markdown_table += f"| {ora_inizio} - {ora_fine} | {l['materia']} | {docente_link} | {aula_link} | {canali_str} | {anni_str} |\n"

    st.markdown(markdown_table)
    st.markdown("---")







                                 




