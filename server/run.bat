set FLASK_APP=server/lmao_server.py
set FLASK_ENV=production
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=(passwd)
set POSTGRES_HOST=localhost

python -m waitress --port 80 --call "lmao_server:create_app"