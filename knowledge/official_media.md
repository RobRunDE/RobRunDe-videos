# Offizielle ROB-RUN-Medien (Steam, © Kefir)

Quelle: https://store.steampowered.com/app/4262460/ – geholt mit `python3 pipeline/fetch_official.py` nach `official/` (nicht im Repo).
Katalog gesichtet am 2026-11-24. Nach Updates neu holen und Liste prüfen (Steam tauscht Bilder aus).

## Regeln
- **Eigenes Gameplay hat immer Vorrang.** Offizielles Material nur unterstützend: max. ~20 % der Laufzeit eines Videos, bevorzugt für Hook, Überblick/Kontext oder wenn eigenes Material zu einem Thema fehlt.
- Nie so verwenden, dass @robrun_de wie der offizielle Kanal wirkt (kein Nachbau von Kefir-Branding, kein „offiziell“). Bei Trailer-Szenen im Video dezent kennzeichnen, z. B. Chip „Offizieller Trailer“.
- Logos/Endcards der Trailer (KEFIR, ROB RUN, „Wishlist on Steam“) nicht verwenden.
- Cinematic-Trailer = Render-Szenen, kein echtes Gameplay → nie als Beleg für Spielmechaniken benutzen, nur für Stimmung/Hook.

## Standbilder (in build.py als `"clip": "official/screenshot_XX.jpg"` – bekommen automatisch eine langsame Kamerafahrt)
| Datei | Inhalt | Gut für |
|---|---|---|
| header.jpg | Key-Art: Figur mit Beutel + Clownsmaske vor Wüste, großes ROB-RUN-Logo | nur Endcard-Stimmung, Logo nicht groß zeigen |
| screenshot_01.jpg | Überfall im Juweliergeschäft „Emporium“: maskierter Räuber mit Waffe, Geldstapel auf dem Tresen, Geiseln | Raub/Überfall, Loot, Hook |
| screenshot_02.jpg | Polizei (Spieler) mit Waffen vor dem Emporium, Streifenwagen „Police Interceptor“ | Polizei, Cops vs. Räuber |
| screenshot_03.jpg | Gefängnishof, Häftlinge in Orange, Anzeige „Jail Time 41 Years“ | Gefängnis/Start „frisch aus dem Knast“, Konsequenzen |
| screenshot_04.jpg | Versteck/Garage: Werkbank mit Loot, Pickup „Heist“, bewaffnete Crew | Hideout, Crew, Lagern von Beute |
| screenshot_05.jpg | Verzweigter Fortschritts-/Skill-Baum mit Item-Icons und Charakterkarte | Progression, Freischaltungen |
| screenshot_06.jpg | Verfolgungsjagd: dunkler Sportwagen zwischen Streifenwagen, Stadt | Flucht, Fahrzeuge, Cops |
| screenshot_07.jpg | Casino/Bar mit Roulette, viele Spielercharaktere | Social Hub, Community, Geld |
| screenshot_08.jpg | Schwarzmarkt-Menü: Tabs Gear/Vehicles/Construction, Waffen (Sturmgewehre, Pistole), Weste, Inventar | Waffen, Ausrüstung, Shop, Preise (nur zeigen, keine Zahlen behaupten) |
| screenshot_09.jpg | Figur vor Grundstück mit Bauplan („Plot Plan“), Haus im Hintergrund | Basisbau, Grundstück |
| screenshot_10.jpg | Gebietskarte mit Hex-Feldern/Territorien | Territorien, Clans, Map |

## Trailer (als `"clip": "official/trailer_0X.mp4"` mit `"in"` = Startsekunde)
### trailer_01.mp4 – „RobRun Official Trailer“ (48,7 s, Gameplay-Szenen, 1080p)
- 0–1 Kefir-Logo ✗ · 2 Räuber stürmen Laden mit Beutel · 4 Lagerhalle, Räuber mit Beute · 6 Wüste aus der Luft · 10 Überfall im Shop (Maske, Waffe auf Kassierer) · 12 Schwarz-weiß-Szene Gebäude von oben · 14 Juwelierladen von oben (Grundriss) · 18 Schusswechsel an Wohnwagen + Pickup in der Wüste · 20–22 Polizei im Nachtclub-Feuergefecht · 24 Polizeiauto-Fahrt · 26 Tresortür (Bank-Vault) · 28 Eingang Bank, bewaffneter Spieler · 30 Feuergefecht in der Lobby · 32 Straße von oben mit Autos · 34 große Spielergruppe mit Sportwagen (Clan) · 36–42 Territorialkarte mit Clan-Kämpfen ✓ · 44–48 Logo ✗

### trailer_02.mp4 – „Rob Run Official Cinematic Trailer“ (154 s, Render-Cinematic, KEIN Gameplay)
- 5 Pickup in Wüste · 15–25 Protagonist Close-up · 30 Geldbündel im Sand · 35 Clownsmaske · 41 Räuber im Tresorraum · 46 Überfall im Laden · 51 Magazin wird geladen (Detail) · 56 Szene von oben · 61–66 Räuber mit Helm schießen · 71 Schuss auf Polizeiwagen/Explosion · 92–97 Polizei-Scheinwerfer in der Nacht · 102 Explosion von oben · 107–127 Protagonist Close-ups · 138+ Logo/„Wishlist on Steam“ ✗
