# Arc Overhang fuer OrcaSlicer 2.5
Version 0.2.2  -  24.10.2026  -  experimentell

Portierung von https://github.com/Kelsch/arc-overhang-orcaslicer-integration
auf Orcas natives Python-Pluginsystem. Grundlage ist der konzentrische
Arc-Algorithmus von Steven McCulloch, Nicolai Wachenschwan und Kelsch.

## Installation
1. ZIP entpacken.
2. In OrcaSlicer 2.5 das Menue **Plugins** oeffnen.
3. **Install local plugin** waehlen und **dist/arc_overhang.py** installieren.
   Diese Variante hat einen stabilen Dateinamen fuer spaetere Updates.
   Alternativ ist die enthaltene .whl installierbar. Nur eine Variante installieren.
4. Orca installiert NumPy und Shapely automatisch in seiner Python-Umgebung.
   Fuer diese erste Installation braucht Orca Internetzugang.
5. Das Plugin und beide Faehigkeiten **Arc Overhang** aktivieren: **Pages** fuer den Tab und **Slicing Pipeline** fuer die Verarbeitung.
6. Im erweiterten Modus unter **Process > Others > Slicing Pipeline Plugin**
   **Arc Overhang** auswaehlen und das Prozessprofil speichern.
7. Oben im Hauptfenster den neuen Tab **Arc Overhang** oeffnen und Einstellungen anpassen. Der Config-Dialog der Pipeline-Faehigkeit bleibt ebenfalls nutzbar.
   Der separate Bereich **Post-processing scripts** bleibt fuer dieses Plugin leer.

Orca 2.4 und aeltere Versionen haben diese Plugin-Schnittstelle nicht.
Die Schnittstelle wurde mit dem Quellcode des Tags **v2.5.0-alpha**
abgeglichen. Die automatische Registrierung wurde mit einem Host-Testdouble
geprueft; die Installation und Ausfuehrung in der echten Orca-Oberflaeche
wurden noch nicht getestet.

## Update von 0.1 / 0.2
Alte Arc-Overhang-Plugins im Plugin-Dialog deaktivieren. Nach Installation der
neuen Datei die neue Pipeline-Faehigkeit im Prozessprofil neu auswaehlen;
das bisherige Profil verweist sonst weiterhin auf die alte Plugin-Identitaet.
Die alten versionierten WHL-Dateien wurden von Orca getrennt installiert und
hatten getrennte Einstellungen. Beim Wechsel zur stabil benannten .py-Datei
die benoetigten Werte einmal neu setzen. Spaetere Updates derselben .py-Datei
koennen dieselbe Identitaet weiterverwenden.
Das normale Prozessprofil nach dem Aendern speichern.

## Retraktionskorrektur in 0.2.2
Die Fehlermeldung wurde am aktuellen G-Code reproduziert: Ein Rest von
0.00027 mm aus gerundeten Wipe-Bewegungen wurde als fortbestehende
Retraktion gewertet. Positive Extrusion wird jetzt auch waehrend XY-Fahrten
gegen den Rueckzug gerechnet. Nach einer positiven Rueckfoerderung werden
Reste unter 0.0005 mm als Rundungsrauschen behandelt. Wirklich noch
zurueckgezogene Feature-Grenzen bleiben geschuetzt und melden Start-/Endwert.

## Weitere behobene Probleme
- Kein Nachladen von utf-8-sig: kein dadurch verursachtes Lesen/Schreiben
  zufaelliger Python-Cachedateien unter Program Files beim Export.
- Der Save-Knopf ist ein normaler Button. Orcas Konfigurations-iframe erlaubt
  Skripte, aber keine Formulare; ein Submit-Button war dort ungeeignet.
- Native Konfiguration wartet auf onConfig-Bestaetigung des Hosts und meldet
  Timeout oder Schreibschutz anstatt voreilig Erfolg zu behaupten.
- G2/G3-Bahnen werden fuer die Geometrieanalyse angenaehert; unberuehrte
  Originalbahnen bleiben unveraendert.
- Geometrische Ueberhangerkennung auch ohne spezielles Overhang-wall-Label.
- Scarf-Konturen werden ueber ihre XY-Projektion mit geschlossenen Schleifen
  erkannt, ohne lange offene Wege einfach per Gerade zu schliessen.
- M73-Druckzeitmeldungen im Bridge-Block blockieren die Ersetzung nicht mehr.
- Im Tab zeigt Aktualisieren das Ergebnis oder den Fehler des letzten Exports.

Die Sicherheitsabfragen werden nicht automatisch mit Ja beantwortet.
Stattdessen entfaellt der konkret festgestellte unnoetige Codec-Zugriff.
Der eigentliche G-Code-Ordner wird vom Host fuer den Export freigegeben.

## Wo der neue Tab sitzt
**Arc Overhang** erscheint oben neben **Prepare**, **Preview** und **Device**.
Die linken Prozessbereiche **Qualitaet**, **Staerke** und weitere bleiben bestehen.
Der Tab ersetzt keinen dieser Bereiche.

Tab und Pipeline verwenden dieselbe Konfiguration. Der Tab zeigt die fuer das
aktive Profil gueltigen Werte. Speichern im Tab setzt die globalen Vorgaben.
Falls ein Profil eigene Plugin-Ueberschreibungen besitzt, haben diese weiterhin
Vorrang; der Tab weist nach dem Speichern darauf hin. Solche Werte im
Prozessprofil unter **Plugin Configuration** anpassen.
Mit **Aktualisieren** lassen sich Werte nach einem Profilwechsel neu laden.

Die Pipeline muss einmal im Prozessprofil ausgewaehlt werden. Danach kann
die normale Bedienung ueber den neuen Tab erfolgen. Nur den Tab zu aktivieren
schaltet die G-Code-Verarbeitung nicht automatisch ein.

## Benutzung
Modell normal slicen und G-Code exportieren. Die Verarbeitung erfolgt im
Pipeline-Schritt **psGCodePostProcess** auf der Arbeitsdatei des Exports.
In anderen Pipeline-Schritten tut das Plugin nichts.

**Die normale Slicing-Vorschau zeigt diesen Export-Schritt nicht.**
Zur Kontrolle die exportierte G-Code-Datei neu im G-Code-Viewer oeffnen.
Die Slicer-Zeit- und Materialangaben werden durch das Plugin nicht neu berechnet.
Bei Bambu-Druckern wird der vom Host gelieferte G-Code-Text verarbeitet;
das Plugin bearbeitet keine selbst eingelesenen 3MF-Archive.

Arc Overhang ersetzt geeignete Bridge-Fuellungen, die an Overhang-Waende grenzen.
Es benoetigt ein Bridge-Feature im G-Code. Zusaetzliche Overhang-wall-Labels
sind hilfreich; fehlen sie, wird der Ueberhang geometrisch gegen die
darunterliegende Schicht geprueft. Support fuer die zu ersetzende
Flaeche entsprechend deaktivieren. Die Overhang-Wanderkennung muss aktiv sein.

Der Parser benoetigt absolute XYZ-Koordinaten (G90), relative Extrusion (M83),
Text-G-Code mit Feature-Kommentaren und lineare Druckbewegungen (G1).
G2/G3-Arc-Fitting mit relativen I/J-Zentren oder R ist unterstuetzt.
Geschlossene Aussenkonturen werden benoetigt; Scarf-Ueberlappungen der Waende
werden projiziert. Nicht-planare Bridge-Bahnen bleiben ausgeschlossen.
Einzelwerkzeug/Einzelmaterial ist der vorgesehene Einsatzfall.
Vase-/Spiral-Modus, IDEX, Werkzeugwechsel, volumetrische Extrusion und
Firmware-Retraktion werden nicht unterstuetzt.

Temperatur, Bauteilluefter, Aux-Luefter und Gehaeuseluefter werden nicht geaendert.
Die am ersetzten Bridge-Abschnitt aktiven Werte gelten weiter.
Die eingestellte Plugin-Retraktion muss zu deinem Drucker passen.
Z-Hop waehrend der erzeugten Arc-Fahrten ist in dieser Version nicht enthalten.

## Wichtige Einstellungen
| Einstellung in der Maske | JSON-Schluessel | Standard | Wirkung |
|---|---|---:|---|
| Arc-Geschwindigkeit | arc_speed_mm_s | 1.5 mm/s | Obergrenze der Geschwindigkeit auf Arc-Bahnen |
| Minimale Arc-Geschwindigkeit | minimum_arc_speed_mm_s | 0.5 mm/s | Untergrenze fuer kurze Arcs |
| Arc-Abstand / Duesendurchmesser | arc_spacing_nozzle_ratio | 0.95 | Bahnabstand als Faktor des Duesendurchmessers |
| Verankerung in der Wand | wall_overlap_mm | 0.8 mm | Erweiterung der Arc-Region in die Wand, begrenzt durch die aktuelle Aussenkontur |
| Versatz des Arc-Mittelpunkts | arc_center_offset_mm | 2 mm | Reduziert sehr kleine Arcs; 0 erreicht engere Stellen |
| Maximaler Radius | max_radius_mm | 100 mm | Groesster Arc-Radius |
| Minimale Flaeche | minimum_area_mm2 | 50 mm2 | Kleinere Bereiche bleiben als Originalbruecke erhalten |
| Minimale Ueberhanglaenge | minimum_overhang_length_mm | 5 mm | Mindestlaenge eines angrenzenden Overhang-Wandsegments |
| Arc-Flow | flow_multiplier | 1.35 | Faktor auf den kreisfoermigen Fadenquerschnitt des Originalalgorithmus; Profil-Flow wird zusaetzlich beruecksichtigt |
| Minimale Zeit pro Arc | minimum_arc_time_s | 3 s | Kurze Arcs werden bis zur Mindestgeschwindigkeit verlangsamt |
| Erforderliche Flaechenabdeckung | minimum_coverage_percent | 90 % | Darunter bleibt die gesamte Feature-Bruecke unveraendert |
| Retraktion | retract_length_mm | 0.8 mm | Retraktion fuer Fahrten zwischen Arc-Bahnen; 0 schaltet sie aus |

**Beispiel Abstand:** 0.5 bei einer 0.4-mm-Duese ergibt 0.2 mm Bahnabstand.
Das ist ein Abstandsfaktor, kein Wert in Millimetern und keine Prozentangabe.
Wandverankerung und Bahnabstand sind unabhaengige Einstellungen.

Fuer einen Versuch mit bis zu 10 mm/s **Arc-Geschwindigkeit** auf 10 setzen.
Kurze Arcs werden wegen der Mindestzeit weiterhin langsamer gedruckt.
Wenn alle Arcs exakt mit 10 mm/s laufen sollen, auch die minimale
Arc-Geschwindigkeit auf 10 setzen. Das ist kein automatisch druckvalidiertes Profil.

Das Füllmuster der direkt folgenden Schicht ist auswählbar. Standardmäßig
bleibt Orças ursprüngliches Muster erhalten. Optional kann das Plugin massive
Innenfüllung im Bereich ersetzter Bridge-Bahnen durch eine Hilbert-Kurve ersetzen.
Andere Füllbereiche bleiben erhalten. Die Hilbert-Option kann die Druckzeit erhöhen
und ist experimentell; vor dem Druck den erzeugten G-Code prüfen.

## Wenn nichts geaendert wird
- Erzeugt Orca ein Bridge-Feature und eine geometrisch ungestuetzte Flaeche?
- Ist die Faehigkeit im Prozessprofil ausgewaehlt?
- Wurde bereits exportiert und die exportierte Datei neu geoeffnet?
- Ist der Bereich mindestens 50 mm2 gross und die angrenzende Overhang-Bahn lang genug?
- Kann die darunterliegende Aussenkontur als geschlossener Ring rekonstruiert werden?
- Die Meldung im Python-Log nennt ersetzte und uebersprungene Features.
- Im geaenderten G-Code steht **; ARC_OVERHANG_PLUGIN:**.

Nicht rekonstruierbare, nicht verankerte oder nicht ausreichend gefuellte
Bereiche bleiben unveraendert. Bei einem ungeeigneten Einzelbereich wird der
gesamte betreffende Bridge-Feature-Block erhalten; andere Features werden
getrennt behandelt. Bei einem Fehler wird die Exportdatei nicht ersetzt.

## Enthaltene Dateien
- dist/*.whl: installierbares Plugin-Paket
- dist/arc_overhang.py: installierbare Einzeldatei, zugleich lesbarer Quellcode
- adapter.py.in und build_plugin.py: reproduzierbare Portierung
- upstream/: originale SoftFever-Datei und GPL-Lizenz
- test_audit.py: Ausfuehrung mit gesperrten externen Dateizugriffen
- REAL_FILE_VALIDATION.json: Pruefergebnis am aktuellen Orca-G-Code (ohne Modelldaten)
- tests.py: automatisierte Engine-, Parser-, Dateischreib- und Schnittstellentests
- test_ui.js, test_tab.js und die beiden preview.html-Dateien: isolierter Test der Einstellungsmaske
- examples/: synthetische Vorher-/Nachher-Dateien fuer die G-Code-Analyse
- VALIDATION.md: durchgefuehrte und noch offene Pruefungen
- LICENSE und THIRD_PARTY_NOTICES.md: Lizenz und Herkunft

Die Beispieldateien sind synthetische Testdaten ohne druckerspezifischen
Start-/Endcode und nicht zum Drucken gedacht.

## Entwicklung
Python 3.12 oder neuer und NumPy/Shapely installieren:

    python -m pip install "numpy>=1.26,<3" "shapely>=2.0,<3"
    python build_plugin.py
    python tests.py
    python test_audit.py

Optional fuer den separaten JavaScript-Test:

    node test_ui.js
    node test_tab.js

test_ui.js verwendet die mit Orca installierte Datei plugin-config-ui.js.
Bei abweichendem Installationspfad ORCA_CONFIG_BRIDGE_PATH setzen.

Das Plugin nutzt keine externen Programme, Netzverbindungen oder zusaetzliche
GUI-Toolkits. Die Paketinstallation der Abhaengigkeiten uebernimmt Orca.
Die Ausgabe wird zunaechst in eine temporaere Datei im G-Code-Verzeichnis
geschrieben und erst nach erfolgreicher Verarbeitung atomar ersetzt.

## Herkunft und Lizenz
GPL-3.0; keine Gewaehrleistung. Originalidee und fruehe Implementierung:
Steven McCulloch. Slicer-Integration: Nicolai Wachenschwan.
Orca/SoftFever-Anpassung: Kelsch. Portierung und Aenderungen: 24.10.2026.

Quellen:
- https://github.com/Kelsch/arc-overhang-orcaslicer-integration
- https://github.com/nicolai-wachenschwan/arc-overhang-prusaslicer-integration
- https://github.com/stmcculloch/arc-overhang
- https://github.com/OrcaSlicer/OrcaSlicer/wiki/plugin_development
- https://github.com/OrcaSlicer/OrcaSlicer/wiki/pages
- https://github.com/OrcaSlicer/OrcaSlicer/blob/v2.5.0-alpha/src/slic3r/plugin/pluginTypes/slicingPipeline/SlicingPipelinePluginCapability.cpp


Das Füllmuster der Folgeschicht ist auswählbar: Standardmäßig bleibt Orças Muster erhalten. Optional kann in geeigneten Bereichen mit massiver Innenfüllung über ersetzten Arc-Bereichen eine Hilbert-Kurve verwendet werden. Das kann die Druckzeit erhöhen; andere Füllbereiche bleiben unverändert.


Druckreihenfolge auf betroffenen Schichten: normale Wände und Infill, danach Arcs, zuletzt Overhang-Walls. Vorhandene Werkzeugwechsel bleiben erhalten; die Reihenfolge wird innerhalb des jeweiligen Werkzeugabschnitts angewendet.
