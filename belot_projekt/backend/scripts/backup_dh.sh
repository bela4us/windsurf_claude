#!/bin/bash
#
# Skripta za izradu sigurnosnih kopija PostgreSQL baze podataka Belot aplikacije
#
# Ova skripta stvara sigurnosne kopije baze podataka s vremenskim oznakama,
# upravlja rotacijom starih kopija, i podržava različite okoline (dev, prod).
#
# Korištenje: ./backup_db.sh [dev|prod] [broj_dana_čuvanja]
#   - Prvi argument određuje okolinu (dev ili prod, zadano: dev)
#   - Drugi argument određuje koliko dana čuvati backupe (zadano: 7)
#
# Primjeri:
#   ./backup_db.sh                 # Backup dev baze, čuvaj 7 dana
#   ./backup_db.sh prod            # Backup prod baze, čuvaj 7 dana
#   ./backup_db.sh prod 30         # Backup prod baze, čuvaj 30 dana

set -e  # Prekini izvršavanje ako dođe do greške

# Konfiguracija
BACKUP_DIR="/var/backups/belot"    # Direktorij za sigurnosne kopije
DEV_DB_NAME="belot_dev"            # Ime razvojne baze
PROD_DB_NAME="belot_prod"          # Ime produkcijske baze
DEV_DB_USER="belot_dev"            # Korisnik razvojne baze
PROD_DB_USER="belot_prod"          # Korisnik produkcijske baze
DEV_DB_HOST="localhost"            # Host razvojne baze
PROD_DB_HOST="db.belot.example.com" # Host produkcijske baze
DEFAULT_RETENTION_DAYS=7           # Zadani broj dana za čuvanje backupa

# Parsiranje argumenata
ENVIRONMENT=${1:-dev}              # Prvi argument je okolina (dev/prod), zadano: dev
RETENTION_DAYS=${2:-$DEFAULT_RETENTION_DAYS}  # Drugi argument je broj dana čuvanja, zadano: 7

# Validacija argumenata
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Greška: Prvi argument mora biti 'dev' ili 'prod'."
    echo "Korištenje: $0 [dev|prod] [broj_dana_čuvanja]"
    exit 1
fi

if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
    echo "Greška: Drugi argument mora biti broj dana (cijeli broj)."
    echo "Korištenje: $0 [dev|prod] [broj_dana_čuvanja]"
    exit 1
fi

# Postavljanje varijabli na temelju okoline
if [[ "$ENVIRONMENT" == "dev" ]]; then
    DB_NAME=$DEV_DB_NAME
    DB_USER=$DEV_DB_USER
    DB_HOST=$DEV_DB_HOST
    echo "Korištenje razvojne okoline."
else
    DB_NAME=$PROD_DB_NAME
    DB_USER=$PROD_DB_USER
    DB_HOST=$PROD_DB_HOST
    echo "Korištenje produkcijske okoline."
fi

# Stvaranje direktorija za sigurnosne kopije ako ne postoji
FULL_BACKUP_DIR="$BACKUP_DIR/$ENVIRONMENT"
if [ ! -d "$FULL_BACKUP_DIR" ]; then
    echo "Stvaranje direktorija za sigurnosne kopije: $FULL_BACKUP_DIR"
    mkdir -p "$FULL_BACKUP_DIR"
fi

# Generiranje naziva datoteke s vremenskom oznakom
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="$FULL_BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Izvršavanje sigurnosne kopije
echo "Izrađujem sigurnosnu kopiju baze $DB_NAME na $DB_HOST..."
if pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --format=custom | gzip > "$BACKUP_FILE"; then
    echo "Sigurnosna kopija uspješno izrađena: $BACKUP_FILE"
else
    echo "Greška prilikom izrade sigurnosne kopije!"
    exit 1
fi

# Rotacija starih sigurnosnih kopija
echo "Brišem sigurnosne kopije starije od $RETENTION_DAYS dana..."
find "$FULL_BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

# Izlistaj preostale sigurnosne kopije
echo "Trenutne sigurnosne kopije:"
ls -lh "$FULL_BACKUP_DIR" | grep "${DB_NAME}_"

# Izračunaj ukupnu veličinu sigurnosnih kopija
TOTAL_SIZE=$(du -sh "$FULL_BACKUP_DIR" | cut -f1)
echo "Ukupna veličina sigurnosnih kopija: $TOTAL_SIZE"

echo "Proces izrade sigurnosne kopije završen."

# Optional: Exportranje na Cloud Storage (S3, Google Cloud, itd.)
if [[ "$ENVIRONMENT" == "prod" ]]; then
    # Ovdje bi došao kod za slanje kopije na cloud storage
    # Primjer za AWS S3:
    # if command -v aws &> /dev/null; then
    #     echo "Uploading backup to S3..."
    #     aws s3 cp "$BACKUP_FILE" "s3://belot-backups/$(basename "$BACKUP_FILE")"
    # fi
    
    echo "Za produkciju: dodaj kod za slanje kopije na cloud storage."
fi

exit 0