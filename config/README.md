# Local configuration
Copy local.env.example to .env at the project root before the first launch.
Compose reads that root .env and passes the selected dates to the containers.
The end date is exclusive. src/settings.py validates the selected interval.
Service settings and local demo credentials are in compose.yaml.
