# Inversor IA

**Autor acreditado:** Claudio Damián López

Aplicación web experimental con API FastAPI para analizar criptomonedas (Binance) y acciones (cotizaciones públicas), y ejecutar órdenes **solo en una cuenta virtual**. No conecta claves privadas de Binance ni opera dinero real.

## Instalación local

Requiere Python 3.11+.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

Abrí http://127.0.0.1:8000. El botón de inicio solo cambia el estado del simulador: **no existe todavía un ciclo de operaciones automáticas**. Las compras y ventas virtuales se ejecutan por el endpoint `/api/paper-order`, con un máximo por compra del 10% del capital inicial. El botón de parada impide futuras operaciones automáticas cuando se implemente el ciclo, pero **no cancela órdenes reales ni cierra posiciones**. No hay IA entrenada: las señales son reglas de medias móviles y RSI.

## Seguridad

**No desplegar públicamente sin autenticación, control de acceso, TLS y limitación de peticiones.** La API actual no tiene inicio de sesión. El repositorio público contiene solo código, sin claves API. La base SQLite se crea localmente y está excluida de Git.

## Limitaciones

Las fuentes públicas de cotizaciones pueden fallar o aplicar límites. No hay ejecución real, predicción garantizada, control de riesgo integral, backtesting validado ni aplicación Android nativa. La interfaz web es responsive, pero aún no es una PWA instalable completa.
