# API Reference

TunnBox provides a RESTful API for automation.

## Authentication

All endpoints (except login/setup) require a Bearer Token.

`Authorization: Bearer <access_token>`

## Base URL

`/api`

## Endpoints

*   **Auth**: `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`
*   **System**: `/api/system/info`, `/api/system/stats`, `/api/health`
*   **Interfaces**: `/api/interfaces` (GET, POST), `/api/interfaces/{name}` (DELETE, PUT)
*   **Peers**: `/api/peers` (GET, POST), `/api/peers/{id}` (DELETE, PUT)
*   **Peer Configs**: `/api/peers/{id}/config`, `/api/peers/{id}/qrcode`

## Documentation

For full interactive documentation (Swagger UI), start the server and visit:
`http://localhost:8000/docs`
