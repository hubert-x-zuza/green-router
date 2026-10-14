# Wdrożenie publiczne (maszyna wirtualna Azure + HTTPS)

Cel: jury otwiera aplikację pod adresem `https://<nazwa>.<region>.cloudapp.azure.com`, bez instalowania
czegokolwiek. Jedna maszyna wirtualna uruchamia ten sam `docker compose`, co w README, a przed nim stoi
Caddy, który sam pobiera certyfikat HTTPS. Dane przetworzone (`data/processed/`) budujemy raz lokalnie
i kopiujemy na maszynę, żeby nie powtarzać pobierania z Overpass i MSIP (regulamin MSIP ogranicza
intensywne użycie usług, patrz D-010).

Polecenia `az` poniżej nie były uruchamiane przez autora dokumentu; sprawdź flagi przez `az vm create --help`.

## 1. Maszyna wirtualna

```sh
az vm create --resource-group <GRUPA> --name zdrowa-trasa --image Ubuntu2204 \
  --size Standard_B2ms --admin-username azureuser --generate-ssh-keys \
  --public-ip-sku Standard --public-ip-address-dns-name <NAZWA>
az vm open-port --resource-group <GRUPA> --name zdrowa-trasa --port 80  --priority 900
az vm open-port --resource-group <GRUPA> --name zdrowa-trasa --port 443 --priority 901
```

- `Standard_B2ms` ma 2 vCPU i 8 GB RAM; API potrzebuje około 1 GB.
- Adres aplikacji: `<NAZWA>.<region>.cloudapp.azure.com` (region widać w wyniku `az vm create`).
- `az vm create` domyślnie otwiera SSH (22) dla wszystkich. W portalu Azure (Sieć > reguły portów
  przychodzących) ogranicz port 22 do swojego adresu IP.
- Port 8080 pozostaje zamknięty. Nie otwieraj go.

## 2. Docker na maszynie

```sh
ssh azureuser@<NAZWA>.<region>.cloudapp.azure.com
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker azureuser && exit     # wyloguj się i zaloguj ponownie
docker compose version                        # wymagane >= 2.24
```

## 3. Kod na maszynie

Najpierw wypchnij zmiany (pliki `docker-compose.prod.yml` i `Caddyfile`) do repozytorium, potem:

```sh
git clone https://github.com/Zuzaj/green-router.git ~/green-router
```

Jeśli repozytorium jest prywatne, użyj tokenu dostępu albo skopiuj kod przez `rsync` (bez `data/raw`,
`.venv`, `web/node_modules`).

## 4. Dane: jednorazowa kopia z Twojego komputera

Na swoim komputerze, w katalogu projektu (po `make data`):

```sh
rsync -avz data/processed/ azureuser@<NAZWA>.<region>.cloudapp.azure.com:~/green-router/data/processed/
```

To około 174 MB i zawiera także `air_history.sqlite` (dotychczasowa historia powietrza).

API czyta przy starcie także cztery małe pliki z `data/raw/` (razem około 2 MB). Bez
`city_boundary` API się nie uruchomi; brak pozostałych nie powoduje błędu, ale po cichu wyłącza
infrastrukturę rowerową, pitniki i dopasowanie miejsc w linku Google Maps:

```sh
rsync -avz --relative data/raw/city_boundary data/raw/cycle_infra data/raw/fountains_outdoor \
  data/raw/osm/poi.parquet azureuser@<NAZWA>.<region>.cloudapp.azure.com:~/green-router/
```
Zatrzymaj wtedy lokalnego archiwizatora, żeby historia nie rozjechała się na dwa pliki:

```sh
launchctl bootout gui/$(id -u)/pl.zdrowatrasa.air
```

## 5. Uruchomienie

Na maszynie:

```sh
cd ~/green-router
echo 'DOMAIN=<NAZWA>.<region>.cloudapp.azure.com' > .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Pierwsze uruchomienie buduje obrazy (kilka minut). Usługa `air` przy pierwszym przebiegu pobiera
metadane stacji GIOŚ (limit 2 zapytania na minutę, około 5 minut), a potem pobiera dane co godzinę.
Certyfikat HTTPS pojawia się po kilkudziesięciu sekundach: `docker compose logs caddy`.

## 6. Sprawdzenie (z telefonu w sieci komórkowej, nie z domowego wi-fi)

1. `https://<NAZWA>.<region>.cloudapp.azure.com` otwiera aplikację, kłódka w pasku adresu.
2. Trasa piesza i rowerowa, wyszukiwanie adresu, zakładka „Dla miasta”.
3. Plakietka powietrza pokazuje godzinę danych i zmienia się po godzinie.
4. `https://<NAZWA>.<region>.cloudapp.azure.com/api/v1/health` zwraca poprawną odpowiedź.

## Utrzymanie

- Restart po zmianie danych: `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api`.
- Aktualizacja kodu: `git pull` i ponownie polecenie `up --build -d` z kroku 5.
- Kopia zapasowa historii powietrza: `scp azureuser@<...>:~/green-router/data/processed/air_history.sqlite .`
- Utrzymuj maszynę do końca oceny konkursu. Nagraj też krótki film z działania na wypadek słabego łącza.
- Prywatność: Caddy, nginx i uvicorn nie zapisują logów dostępu (zapytania mogą zawierać adres).
