belot_projekt/
├── backend/
│   ├── belot/                        # Glavna aplikacija
│   │   ├── __init__.py
│   │   ├── asgi.py                   # ASGI konfiguracija za WebSockets
│   │   ├── settings/                 # Razdvojene postavke za različite okoline
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Osnovne postavke
│   │   │   ├── development.py        # Razvojne postavke
│   │   │   ├── production.py         # Produkcijske postavke
│   │   │   └── testing.py            # Postavke za testiranje
│   │   ├── urls.py                   # URL rute
│   │   └── wsgi.py
│   ├── game/                         # Aplikacija za igru
│   │   ├── __init__.py
│   │   ├── admin.py                  # Admin sučelje
│   │   ├── consumers.py              # WebSocket potrošači
│   │   ├── models/                   # Razdvojeni modeli podataka
│   │   │   ├── __init__.py
│   │   │   ├── game.py               # Model igre
│   │   │   ├── round.py              # Model runde
│   │   │   └── move.py               # Model poteza
│   │   ├── repositories/             # Repozitoriji za pristup podacima
│   │   │   ├── __init__.py
│   │   │   ├── game_repository.py    # Repozitorij za igru
│   │   │   └── move_repository.py    # Repozitorij za poteze
│   │   ├── services/                 # Sloj usluga za poslovnu logiku
│   │   │   ├── __init__.py
│   │   │   ├── game_service.py       # Usluge za igru
│   │   │   └── scoring_service.py    # Usluge za bodovanje
│   │   ├── routing.py                # WebSocket rute
│   │   ├── serializers/              # Razdvojeni serializatori
│   │   │   ├── __init__.py
│   │   │   ├── game_serializers.py   # Serializatori za igru
│   │   │   └── move_serializers.py   # Serializatori za poteze
│   │   ├── views/                    # Razdvojeni pogledi
│   │   │   ├── __init__.py
│   │   │   ├── game_views.py         # Pogledi za igru
│   │   │   └── api_views.py          # API pogledi
│   │   ├── events/                   # Event-driven arhitektura
│   │   │   ├── __init__.py
│   │   │   ├── handlers.py           # Event handleri
│   │   │   └── events.py             # Definicije događaja
│   │   ├── tests/                    # Testovi za igru
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py        # Testovi za modele
│   │   │   ├── test_views.py         # Testovi za poglede
│   │   │   ├── test_services.py      # Testovi za usluge
│   │   │   └── test_game_logic.py    # Testovi za logiku igre
│   │   └── game_logic/               # Logika igre
│   │       ├── __init__.py
│   │       ├── card.py               # Klasa karte
│   │       ├── deck.py               # Špil karata
│   │       ├── game.py               # Glavna logika igre
│   │       ├── player.py             # Klasa igrača
│   │       ├── rules.py              # Pravila belota
│   │       ├── scoring.py            # Sustav bodovanja
│   │       └── validators/           # Validatori za pravila igre
│   │           ├── __init__.py
│   │           ├── move_validator.py # Validacija poteza
│   │           └── call_validator.py # Validacija zvanja
│   ├── lobby/                        # Aplikacija za predvorje igre
│   │   ├── ...                       # (slična struktura kao game)
│   ├── users/                        # Aplikacija za korisnike
│   │   ├── ...                       # (slična struktura kao game)
│   ├── stats/                        # Aplikacija za statistiku
│   │   ├── ...                       # (slična struktura kao game)
│   ├── utils/                        # Zajedničke pomoćne funkcije
│   │   ├── __init__.py
│   │   ├── helpers.py
│   │   ├── decorators.py             # Prilagođeni dekoratori
│   │   └── exceptions.py             # Prilagođene iznimke
│   ├── middleware/                   # Prilagođeni middleware
│   │   ├── __init__.py
│   │   ├── auth_middleware.py
│   │   └── rate_limiter.py           # Limitiranje zahtjeva
│   ├── celery_app/                   # Celery za asinkrone zadatke
│   │   ├── __init__.py
│   │   ├── tasks.py                  # Definicije zadataka
│   │   └── celery.py                 # Konfiguracija Celery-a
│   ├── cache/                        # Konfiguracija keširanje
│   │   ├── __init__.py
│   │   └── redis_cache.py            # Integracija s Redis-om
│   ├── manage.py
│   ├── requirements/                 # Razdvojeni zahtjevi za različite okoline
│   │   ├── base.txt                  # Osnovne ovisnosti
│   │   ├── dev.txt                   # Razvojne ovisnosti
│   │   ├── prod.txt                  # Produkcijske ovisnosti
│   │   └── test.txt                  # Testne ovisnosti
│   └── scripts/                      # Skripte za upravljanje aplikacijom
│       ├── backup_db.sh              # Sigurnosne kopije baze
│       └── seed_data.py              # Punjenje testnih podataka
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   ├── favicon.ico
│   │   ├── locales/                  # Prijevodi za internacionalizaciju
│   │   │   ├── en/                   # Engleski prijevodi
│   │   │   ├── hr/                   # Hrvatski prijevodi
│   │   │   └── ...                   # Ostali jezici
│   │   └── assets/
│   │       ├── images/
│   │       │   └── cards/            # Slike karata
│   │       └── sounds/               # Zvukovi
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.tsx
│   │   ├── api/                      # API klijent
│   │   │   ├── index.ts              # Glavni API klijent
│   │   │   ├── game.ts               # API za igru
│   │   │   ├── lobby.ts              # API za predvorje
│   │   │   └── user.ts               # API za korisnike
│   │   ├── components/               # React komponente
│   │   │   ├── common/               # Zajedničke komponente
│   │   │   │   ├── ui/               # UI komponente
│   │   │   │   ├── form/             # Komponente za forme
│   │   │   │   └── layout/           # Komponente layouta
│   │   │   ├── game/                 # Komponente za igru
│   │   │   │   ├── Card.tsx          # Komponenta karte
│   │   │   │   ├── Deck.tsx          # Komponenta špila
│   │   │   │   ├── GameTable.tsx     # Komponenta stola
│   │   │   │   ├── Player.tsx        # Komponenta igrača
│   │   │   │   └── Scoreboard.tsx    # Komponenta rezultata
│   │   │   └── lobby/                # Komponente za predvorje
│   │   │       ├── GameList.tsx      # Lista igara
│   │   │       ├── GameRoom.tsx      # Soba za igru
│   │   │       └── UserList.tsx      # Lista korisnika
│   │   ├── state/                    # Upravljanje stanjem
│   │   │   ├── store.ts              # Konfiguracija Redux/Zustand
│   │   │   ├── slices/               # Redux slice-ovi / Zustand store-ovi
│   │   │   │   ├── gameSlice.ts      # Stanje igre
│   │   │   │   ├── userSlice.ts      # Stanje korisnika
│   │   │   │   └── lobbySlice.ts     # Stanje predvorja
│   │   │   └── hooks.ts              # Custom hooks za pristup stanju
│   │   ├── context/                  # React kontekst
│   │   │   ├── AuthContext.tsx       # Kontekst autentifikacije
│   │   │   └── GameContext.tsx       # Kontekst igre
│   │   ├── hooks/                    # Vlastiti React hooks
│   │   │   ├── useWebSocket.ts       # Hook za WebSocket
│   │   │   ├── useAuth.ts            # Hook za autentifikaciju
│   │   │   ├── useLocalStorage.ts    # Hook za lokalnu pohranu
│   │   │   └── useDimensions.ts      # Hook za dimenzije
│   │   ├── pages/                    # Stranice aplikacije
│   │   │   ├── Game.tsx              # Stranica igre
│   │   │   ├── Home.tsx              # Početna stranica
│   │   │   ├── Lobby.tsx             # Stranica predvorja
│   │   │   ├── Login.tsx             # Stranica za prijavu
│   │   │   ├── Profile.tsx           # Stranica profila
│   │   │   └── Register.tsx          # Stranica za registraciju
│   │   ├── utils/                    # Pomoćne funkcije
│   │   │   ├── format.ts             # Funkcije za formatiranje
│   │   │   ├── validation.ts         # Funkcije za validaciju
│   │   │   └── calculations.ts       # Funkcije za izračune
│   │   ├── constants/                # Konstante igre
│   │   │   ├── cards.ts              # Konstante za karte
│   │   │   ├── gameRules.ts          # Konstante za pravila
│   │   │   └── routes.ts             # Konstante za rute
│   │   ├── types/                    # TypeScript tipovi
│   │   │   ├── game.types.ts         # Tipovi za igru
│   │   │   ├── user.types.ts         # Tipovi za korisnike
│   │   │   └── api.types.ts          # Tipovi za API
│   │   ├── animations/               # Animacije
│   │   │   ├── cardAnimations.ts     # Animacije karata
│   │   │   └── transitions.ts        # Tranzicije stranica
│   │   ├── i18n/                     # Internacionalizacija
│   │   │   ├── i18n.ts               # Konfiguracija i18n
│   │   │   └── hooks.ts              # Hooks za i18n
│   │   ├── styles/                   # CSS stilovi
│   │   │   ├── themes/               # Teme (svijetla/tamna)
│   │   │   ├── components/           # Stilovi za komponente
│   │   │   └── global.css            # Globalni stilovi
│   │   └── lib/                      # Eksterne biblioteke i integracije
│   │       ├── analytics.ts          # Analitika
│   │       └── errorReporting.ts     # Izvještavanje o greškama
│   ├── tests/                        # Frontend testovi
│   │   ├── unit/                     # Unit testovi
│   │   ├── integration/              # Integracijski testovi
│   │   └── e2e/                      # End-to-end testovi
│   ├── .storybook/                   # Storybook konfiguracija
│   ├── package.json
│   ├── tsconfig.json                 # TypeScript konfiguracija
│   ├── vite.config.ts                # Vite konfiguracija (moderni build tool)
│   └── jest.config.js                # Jest konfiguracija
├── docker/                           # Docker konfiguracija
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml        # Razvojno okruženje
│   └── docker-compose.prod.yml       # Produkcijsko okruženje
├── nginx/                            # Nginx konfiguracija
│   ├── nginx.conf
│   └── sites-available/              # Konfiguracije za različite domene
├── .github/                          # GitHub konfiguracija
│   ├── workflows/                    # GitHub Actions
│   │   ├── ci.yml                    # Continuous Integration
│   │   └── deploy.yml                # Continuous Deployment
│   └── ISSUE_TEMPLATE/              # Predlošci za probleme
├── docs/                             # Dokumentacija projekta
│   ├── api/                          # API dokumentacija
│   │   ├── swagger.yaml              # OpenAPI specifikacija
│   │   └── postman/                  # Postman kolekcije
│   ├── architecture/                 # Dokumentacija arhitekture
│   │   ├── diagrams/                 # Dijagrami
│   │   └── decisions/                # Arhitekturne odluke
│   ├── game-rules/                   # Pravila igre
│   ├── development/                  # Razvojna dokumentacija
│   │   ├── coding-standards.md       # Standardi kodiranja
│   │   └── git-workflow.md           # Git tijek rada
│   └── operations/                   # Operativna dokumentacija
│       ├── deployment.md             # Upute za deployment
│       ├── monitoring.md             # Upute za nadzor
│       └── scaling.md                # Upute za skaliranje
├── scripts/                          # Skripte za projekt
│   ├── setup.sh                      # Postavljanje razvojnog okruženja
│   └── deploy.sh                     # Skripta za deployment
├── .gitignore
├── .editorconfig                     # Konfiguracija editora
├── .env.example                      # Primjer env varijabli
├── Makefile                          # Naredbe za uobičajene operacije
└── README.md                         # Glavna dokumentacija projekta