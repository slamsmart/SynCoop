# SynCoop

## MongoDB Atlas setup

The backend reads MongoDB configuration from `backend/.env`.

1. Create a MongoDB Atlas cluster.
2. In Atlas, create a database user and allow your current IP address in
   **Network Access**.
3. Copy the Atlas connection string and put it in `backend/.env`:

```env
MONGO_URL=mongodb+srv://<username>:<password>@<cluster-host>/syncoop?retryWrites=true&w=majority&appName=<app-name>
DB_NAME=syncoop
APP_ENV=local
EMERGENT_LLM_KEY=
```

Keep `DB_NAME=syncoop` unless you want a separate database. The app seeds demo
data on startup when the target collections are empty.

For local MongoDB, keep:

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=syncoop
```
