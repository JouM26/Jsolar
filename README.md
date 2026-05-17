# Jsolar

Generador de proformas para sistemas fotovoltaicos en Python.

La aplicacion permite:

- Ingresar datos del cliente.
- Declarar equipos de consumo al inicio y ver potencia total y consumo diario en tiempo real.
- Agregar mas equipos de forma dinamica, incluyendo equipos personalizados.
- Cargar plantillas de equipos para escenarios frecuentes.
- Calcular recomendacion automatica de paneles, inversores y baterias.
- Configurar paneles, inversor y baterias con sus precios.
- Ingresar baterias por voltaje y amperaje para calcular la capacidad nominal del banco.
- Agregar costos adicionales dinamicos por nombre, cantidad, unidad y precio unitario.
- Ver subtotal, IVA y total en tiempo real.
- Generar un PDF con resumen tecnico, recomendacion automatica y condiciones comerciales.
- Guardar cotizaciones en historial local SQLite.
- Filtrar historial por cliente o ciudad.
- Cargar cotizaciones anteriores al formulario.
- Compartir resumen por WhatsApp y email mediante enlaces directos.

## Requisitos

- Python 3.10+
- Dependencias en [requirements.txt](requirements.txt)

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python app_solar.py
```

Para ejecutar la interfaz movil con Flet:

```bash
python app_movil.py
```

Se generara un archivo con formato:

- `Proforma_Nombre_Cliente.pdf`

La app tambien crea una base local `jsolar.db` para historial de cotizaciones.

## Estructura principal

- [app_solar.py](app_solar.py): logica de calculo, validaciones y PDF.
- [app_movil.py](app_movil.py): interfaz movil con formulario de proforma.
- [requirements.txt](requirements.txt): dependencias.

## Flujo recomendado en la app movil

1. Completar primero la seccion de equipos y revisar la demanda total.
2. Ajustar parametros de dimensionamiento y aplicar la recomendacion automatica si corresponde.
3. Definir cliente, empresa, paneles, inversor y baterias.
4. Agregar costos adicionales con cantidad, unidad y precio unitario.
5. Configurar condiciones comerciales de la oferta.
6. Presionar `Generar PDF`.
7. Revisar `Historial de cotizaciones` para recargar una anterior cuando sea necesario.
8. Usar `WhatsApp` o `Email` para abrir el canal de envio con mensaje prellenado.

## Siguiente paso recomendado (app movil)

Para usar esto en celular, conviene separar la logica en un modulo de negocio y montar una interfaz movil con:

- Flet (rapido para apps Python multiplataforma).
- Kivy/KivyMD (mas control visual nativo-movil).

La base actual ya incluye la logica necesaria para integrarla a cualquiera de esas opciones.