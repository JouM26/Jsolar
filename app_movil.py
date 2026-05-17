import json
import os
import sqlite3
from typing import Dict, List
from urllib.parse import quote

import flet as ft

from app_solar import (
    CATALOGO_EQUIPOS_W,
    CONDICIONES_DEFAULT,
    DEFAULT_LOGO_PATH,
    EMPRESA_DEFAULT,
    calcular_dimensionamiento,
    calcular_totales_cotizacion,
    clp,
    generar_presupuesto,
)


DB_PATH = "jsolar.db"
LOGO_PATH = str(DEFAULT_LOGO_PATH)
PALETA = {
    "fondo": ft.Colors.BLUE_GREY_50,
    "tarjeta": ft.Colors.WHITE,
    "borde": ft.Colors.GREY_300,
    "texto": ft.Colors.BLUE_GREY_900,
    "texto_suave": ft.Colors.BLUE_GREY_500,
    "primario": ft.Colors.BLUE_GREY_700,
    "primario_hover": ft.Colors.BLUE_GREY_800,
    "secundario": ft.Colors.GREY_800,
    "superficie": ft.Colors.GREY_100,
    "exito": ft.Colors.GREEN_700,
    "alerta": ft.Colors.AMBER_700,
    "error": ft.Colors.RED_700,
}

PLANTILLAS = {
    "Casa basica": [
        {"nombre": "Refrigerador eficiente", "potencia_w": 150, "cantidad": 1, "horas_uso": 18},
        {"nombre": "Iluminacion LED (por foco)", "potencia_w": 12, "cantidad": 8, "horas_uso": 5},
        {"nombre": "Router", "potencia_w": 12, "cantidad": 1, "horas_uso": 24},
        {"nombre": "Televisor LED 50\"", "potencia_w": 120, "cantidad": 1, "horas_uso": 4},
    ],
    "Bomba solar": [
        {"nombre": "Bomba de agua 1HP", "potencia_w": 746, "cantidad": 1, "horas_uso": 6},
        {"nombre": "Router", "potencia_w": 12, "cantidad": 1, "horas_uso": 24},
    ],
    "Negocio pequeno": [
        {"nombre": "Iluminacion LED (por foco)", "potencia_w": 12, "cantidad": 15, "horas_uso": 8},
        {"nombre": "Televisor LED 50\"", "potencia_w": 120, "cantidad": 2, "horas_uso": 6},
        {"nombre": "Router", "potencia_w": 12, "cantidad": 1, "horas_uso": 24},
        {"nombre": "Refrigerador eficiente", "potencia_w": 150, "cantidad": 1, "horas_uso": 18},
    ],
}


def iniciar_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cotizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            cliente TEXT NOT NULL,
            ciudad TEXT NOT NULL,
            total REAL NOT NULL,
            pdf_path TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()



def guardar_cotizacion(payload: Dict, total: float, pdf_path: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO cotizaciones (fecha, cliente, ciudad, total, pdf_path, payload_json)
        VALUES (datetime('now'), ?, ?, ?, ?, ?)
        """,
        (
            payload["datos_cliente"]["nombre"],
            payload["datos_cliente"]["ciudad"],
            total,
            pdf_path,
            json.dumps(payload, ensure_ascii=True),
        ),
    )
    cotizacion_id = cur.lastrowid
    conn.commit()
    conn.close()
    return cotizacion_id



def listar_cotizaciones(limit: int = 30, filtro: str = "") -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    filtro_like = f"%{filtro.strip()}%"
    cur.execute(
        """
        SELECT id, fecha, cliente, ciudad, total, pdf_path
        FROM cotizaciones
        WHERE (? = '' OR cliente LIKE ? OR ciudad LIKE ?)
        ORDER BY id DESC
        LIMIT ?
        """,
        (filtro.strip(), filtro_like, filtro_like, limit),
    )
    filas = [dict(row) for row in cur.fetchall()]
    conn.close()
    return filas



def obtener_cotizacion(cotizacion_id: int) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT payload_json, pdf_path FROM cotizaciones WHERE id = ?", (cotizacion_id,))
    fila = cur.fetchone()
    conn.close()
    if not fila:
        raise ValueError("No se encontro la cotizacion seleccionada")
    payload = json.loads(fila[0])
    payload["pdf_path"] = fila[1] or ""
    return payload



def a_float(valor: str, nombre_campo: str) -> float:
    texto = (valor or "").strip().replace(",", ".")
    if not texto:
        raise ValueError(f"El campo '{nombre_campo}' es obligatorio")
    try:
        return float(texto)
    except ValueError as exc:
        raise ValueError(f"El campo '{nombre_campo}' debe ser numerico") from exc



def a_float_opcional(valor: str) -> float:
    texto = (valor or "").strip().replace(",", ".")
    if not texto:
        return 0.0
    return float(texto)



def estilo_boton_primario() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        bgcolor={ft.ControlState.DEFAULT: PALETA["primario"]},
        color={ft.ControlState.DEFAULT: ft.Colors.WHITE},
        overlay_color={ft.ControlState.HOVERED: PALETA["primario_hover"]},
        shape=ft.RoundedRectangleBorder(radius=12),
    )



def estilo_boton_secundario() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        color={ft.ControlState.DEFAULT: PALETA["secundario"]},
        side={ft.ControlState.DEFAULT: ft.BorderSide(1, PALETA["borde"])},
        shape=ft.RoundedRectangleBorder(radius=12),
    )



def borde_completo(color: str, ancho: int = 1) -> ft.Border:
    lado = ft.BorderSide(ancho, color)
    return ft.Border(top=lado, right=lado, bottom=lado, left=lado)



def tarjeta_seccion(titulo: str, subtitulo: str, contenido: ft.Control) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(titulo, size=20, weight=ft.FontWeight.BOLD, color=PALETA["texto"]),
                ft.Text(subtitulo, size=12, color=PALETA["texto_suave"]),
                ft.Divider(color=PALETA["borde"]),
                contenido,
            ],
            spacing=10,
        ),
        bgcolor=PALETA["tarjeta"],
        border=borde_completo(PALETA["borde"]),
        border_radius=18,
        padding=18,
    )



def construir_ui(page: ft.Page):
    iniciar_db()

    page.title = "S&M SpA - Proforma Fotovoltaica"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = PALETA["fondo"]
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 18
    page.window_width = 460
    page.window_min_width = 360

    estado = {"archivo": "", "total": 0.0, "cotizacion_id": 0}
    equipos_filas: List[Dict] = []
    costos_filas: List[Dict] = []
    recomendacion_cache = {"valor": None}

    salida = ft.Text("", selectable=True, color=PALETA["texto"])
    resumen_demanda = ft.Text("Potencia total: 0 W | Consumo diario: 0 Wh/dia", color=PALETA["texto"])
    resumen_baterias = ft.Text("Capacidad nominal por bateria: 0 Wh | Banco total: 0 kWh", color=PALETA["texto"])
    resumen_costos = ft.Text("Costos adicionales: $ 0", color=PALETA["texto"])
    resumen_economico = ft.Text("Subtotal: $ 0 | IVA: $ 0 | Total: $ 0", color=PALETA["texto"])
    resumen_recomendacion = ft.Text("Ajusta equipos y parametros para calcular la recomendacion automatica.", color=PALETA["texto"])

    historial = ft.Dropdown(label="Historial de cotizaciones", options=[], dense=True, bgcolor=PALETA["tarjeta"])
    filtro_historial = ft.TextField(label="Buscar cliente o ciudad", bgcolor=PALETA["superficie"], border_radius=12)

    empresa_nombre = ft.TextField(label="Empresa", value=EMPRESA_DEFAULT["nombre"], bgcolor=PALETA["superficie"], border_radius=12)
    empresa_tagline = ft.TextField(label="Descripcion comercial", value=EMPRESA_DEFAULT["tagline"], bgcolor=PALETA["superficie"], border_radius=12)
    empresa_telefono = ft.TextField(label="Telefono empresa", value=EMPRESA_DEFAULT["telefono"], bgcolor=PALETA["superficie"], border_radius=12)
    empresa_email = ft.TextField(label="Email empresa", value=EMPRESA_DEFAULT["email"], bgcolor=PALETA["superficie"], border_radius=12)
    empresa_direccion = ft.TextField(label="Direccion empresa", value=EMPRESA_DEFAULT["direccion"], bgcolor=PALETA["superficie"], border_radius=12)
    empresa_asesor = ft.TextField(label="Asesor comercial", value=EMPRESA_DEFAULT["asesor"], bgcolor=PALETA["superficie"], border_radius=12)

    nombre = ft.TextField(label="Nombre cliente", bgcolor=PALETA["superficie"], border_radius=12)
    ciudad = ft.TextField(label="Ciudad", bgcolor=PALETA["superficie"], border_radius=12)
    email = ft.TextField(label="Email cliente", bgcolor=PALETA["superficie"], border_radius=12)
    telefono = ft.TextField(label="Telefono cliente", bgcolor=PALETA["superficie"], border_radius=12)

    panel_modelo = ft.TextField(label="Panel modelo", value="Monocristalino 550W", bgcolor=PALETA["superficie"], border_radius=12)
    panel_potencia = ft.TextField(label="Panel potencia (W)", value="550", bgcolor=PALETA["superficie"], border_radius=12)
    panel_cantidad = ft.TextField(label="Cantidad paneles", value="8", bgcolor=PALETA["superficie"], border_radius=12)
    panel_precio = ft.TextField(label="Precio unitario panel", value="150000", bgcolor=PALETA["superficie"], border_radius=12)

    inv_modelo = ft.TextField(label="Inversor modelo", value="Hibrido 5kW", bgcolor=PALETA["superficie"], border_radius=12)
    inv_potencia = ft.TextField(label="Inversor potencia (W)", value="5000", bgcolor=PALETA["superficie"], border_radius=12)
    inv_cantidad = ft.TextField(label="Cantidad inversores", value="1", bgcolor=PALETA["superficie"], border_radius=12)
    inv_precio = ft.TextField(label="Precio unitario inversor", value="1200000", bgcolor=PALETA["superficie"], border_radius=12)

    bat_modelo = ft.TextField(label="Bateria modelo", value="Litio 48V", bgcolor=PALETA["superficie"], border_radius=12)
    bat_voltaje = ft.TextField(label="Voltaje (V)", value="48", bgcolor=PALETA["superficie"], border_radius=12)
    bat_amperaje = ft.TextField(label="Amperaje (Ah)", value="100", bgcolor=PALETA["superficie"], border_radius=12)
    bat_cantidad = ft.TextField(label="Cantidad baterias", value="2", bgcolor=PALETA["superficie"], border_radius=12)
    bat_precio = ft.TextField(label="Precio unitario bateria", value="1800000", bgcolor=PALETA["superficie"], border_radius=12)

    horas_solar_pico = ft.TextField(label="Horas solar pico", value="5", bgcolor=PALETA["superficie"], border_radius=12)
    autonomia_dias = ft.TextField(label="Autonomia (dias)", value="1", bgcolor=PALETA["superficie"], border_radius=12)
    profundidad_descarga = ft.TextField(label="DOD (%)", value="80", bgcolor=PALETA["superficie"], border_radius=12)
    eficiencia_sistema = ft.TextField(label="Eficiencia (%)", value="85", bgcolor=PALETA["superficie"], border_radius=12)
    margen_seguridad = ft.TextField(label="Margen (%)", value="120", bgcolor=PALETA["superficie"], border_radius=12)

    vigencia_dias = ft.TextField(label="Vigencia de oferta (dias)", value=str(CONDICIONES_DEFAULT["vigencia_dias"]), bgcolor=PALETA["superficie"], border_radius=12)
    plazo_instalacion = ft.TextField(label="Plazo instalacion", value=CONDICIONES_DEFAULT["plazo_instalacion"], bgcolor=PALETA["superficie"], border_radius=12)
    garantia = ft.TextField(label="Garantia", value=CONDICIONES_DEFAULT["garantia"], multiline=True, min_lines=2, bgcolor=PALETA["superficie"], border_radius=12)
    observaciones = ft.TextField(label="Observaciones", value=CONDICIONES_DEFAULT["observaciones"], multiline=True, min_lines=2, bgcolor=PALETA["superficie"], border_radius=12)

    iva = ft.TextField(label="IVA (%)", value="19", bgcolor=PALETA["superficie"], border_radius=12)
    selector_plantilla = ft.Dropdown(
        label="Plantilla de equipos",
        value="Casa basica",
        options=[ft.dropdown.Option(key=clave, text=clave) for clave in PLANTILLAS],
        bgcolor=PALETA["superficie"],
        border_radius=12,
    )

    equipos_lista = ft.Column(spacing=10)
    costos_lista = ft.Column(spacing=10)

    def notificar(msg: str, ok: bool = True):
        color = PALETA["primario"] if ok else PALETA["error"]
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def opciones_equipo() -> List[ft.dropdown.Option]:
        opciones = [ft.dropdown.Option(key=nombre_op, text=nombre_op) for nombre_op in sorted(CATALOGO_EQUIPOS_W.keys())]
        opciones.append(ft.dropdown.Option(key="Personalizado", text="Personalizado"))
        return opciones

    def construir_paneles() -> Dict:
        return {
            "modelo": panel_modelo.value.strip(),
            "potencia_w": a_float(panel_potencia.value, "panel potencia"),
            "cantidad": a_float(panel_cantidad.value, "cantidad paneles"),
            "precio": a_float(panel_precio.value, "precio panel"),
        }

    def construir_inversor() -> Dict:
        return {
            "modelo": inv_modelo.value.strip(),
            "potencia_w": a_float(inv_potencia.value, "inversor potencia"),
            "cantidad": a_float(inv_cantidad.value, "cantidad inversores"),
            "precio": a_float(inv_precio.value, "precio inversor"),
        }

    def construir_bateria() -> Dict:
        return {
            "modelo": bat_modelo.value.strip(),
            "voltaje_v": a_float(bat_voltaje.value, "voltaje bateria"),
            "amperaje_ah": a_float(bat_amperaje.value, "amperaje bateria"),
            "cantidad": a_float(bat_cantidad.value, "cantidad baterias"),
            "precio": a_float(bat_precio.value, "precio bateria"),
        }

    def construir_empresa() -> Dict:
        return {
            "nombre": empresa_nombre.value.strip(),
            "tagline": empresa_tagline.value.strip(),
            "telefono": empresa_telefono.value.strip(),
            "email": empresa_email.value.strip(),
            "direccion": empresa_direccion.value.strip(),
            "asesor": empresa_asesor.value.strip(),
        }

    def construir_condiciones() -> Dict:
        return {
            "vigencia_dias": int(a_float(vigencia_dias.value, "vigencia")),
            "plazo_instalacion": plazo_instalacion.value.strip(),
            "garantia": garantia.value.strip(),
            "observaciones": observaciones.value.strip(),
        }

    def construir_parametros_dimensionamiento() -> Dict:
        return {
            "horas_solar_pico": a_float(horas_solar_pico.value, "horas solar pico"),
            "autonomia_dias": a_float(autonomia_dias.value, "autonomia"),
            "profundidad_descarga": a_float(profundidad_descarga.value, "DOD") / 100.0,
            "eficiencia_sistema": a_float(eficiencia_sistema.value, "eficiencia") / 100.0,
            "margen_seguridad": a_float(margen_seguridad.value, "margen") / 100.0,
        }

    def recolectar_equipos() -> List[Dict]:
        equipos = []
        for fila in equipos_filas:
            nombre_equipo = fila["nombre"].value.strip()
            if not nombre_equipo:
                continue
            equipos.append(
                {
                    "nombre": nombre_equipo,
                    "potencia_w": a_float(fila["potencia"].value, f"potencia {nombre_equipo}"),
                    "cantidad": a_float(fila["cantidad"].value, f"cantidad {nombre_equipo}"),
                    "horas_uso": a_float(fila["horas"].value, f"horas {nombre_equipo}"),
                }
            )
        if not equipos:
            raise ValueError("Debes agregar al menos un equipo de consumo")
        return equipos

    def recolectar_costos() -> List[Dict]:
        costos = []
        for fila in costos_filas:
            nombre_costo = fila["nombre"].value.strip()
            if not nombre_costo:
                continue
            costos.append(
                {
                    "nombre": nombre_costo,
                    "cantidad": a_float(fila["cantidad"].value, f"cantidad {nombre_costo}"),
                    "unidad": fila["unidad"].value.strip(),
                    "precio": a_float(fila["precio"].value, f"precio {nombre_costo}"),
                }
            )
        return costos

    def construir_payload() -> Dict:
        datos_cliente = {
            "nombre": nombre.value.strip(),
            "ciudad": ciudad.value.strip(),
            "email": email.value.strip(),
            "telefono": telefono.value.strip(),
        }
        if not datos_cliente["nombre"] or not datos_cliente["ciudad"]:
            raise ValueError("Nombre y ciudad son obligatorios")
        return {
            "datos_cliente": datos_cliente,
            "empresa": construir_empresa(),
            "condiciones": construir_condiciones(),
            "parametros_dimensionamiento": construir_parametros_dimensionamiento(),
            "paneles": construir_paneles(),
            "inversor": construir_inversor(),
            "bateria": construir_bateria(),
            "equipos_uso": recolectar_equipos(),
            "costos_adicionales": recolectar_costos(),
            "porcentaje_iva": a_float(iva.value, "iva"),
        }

    def actualizar_resumen_economico(_=None):
        try:
            totales = calcular_totales_cotizacion(
                construir_paneles(),
                construir_inversor(),
                construir_bateria(),
                recolectar_costos(),
                a_float(iva.value, "iva"),
            )
            resumen_economico.value = f"Subtotal: {clp(totales['subtotal'])} | IVA: {clp(totales['iva'])} | Total: {clp(totales['total'])}"
        except Exception:
            resumen_economico.value = "Subtotal: $ 0 | IVA: $ 0 | Total: $ 0"
        page.update()

    def actualizar_recomendacion(_=None):
        try:
            recomendacion = calcular_dimensionamiento(
                recolectar_equipos(),
                construir_paneles(),
                construir_inversor(),
                construir_bateria(),
                **construir_parametros_dimensionamiento(),
            )
            recomendacion_cache["valor"] = recomendacion
            resumen_recomendacion.value = (
                f"Paneles: {recomendacion['paneles_recomendados']} recomendados / {int(recomendacion['paneles_actuales'])} configurados | "
                f"Inversores: {recomendacion['inversores_recomendados']} / {int(recomendacion['inversores_actuales'])} | "
                f"Baterias: {recomendacion['baterias_recomendadas']} / {int(recomendacion['baterias_actuales'])}"
            )
        except Exception as exc:
            recomendacion_cache["valor"] = None
            resumen_recomendacion.value = f"Recomendacion no disponible: {exc}"
        page.update()

    def actualizar_resumen_equipos(_=None):
        potencia_total = 0.0
        consumo_total = 0.0
        equipos_validos = 0
        for fila in equipos_filas:
            nombre_equipo = fila["nombre"].value.strip()
            if not nombre_equipo:
                continue
            try:
                potencia = a_float(fila["potencia"].value, f"potencia {nombre_equipo}")
                cantidad = a_float(fila["cantidad"].value, f"cantidad {nombre_equipo}")
                horas = a_float(fila["horas"].value, f"horas {nombre_equipo}")
            except ValueError:
                continue
            equipos_validos += 1
            potencia_total += potencia * cantidad
            consumo_total += potencia * cantidad * horas
        resumen_demanda.value = (
            f"Equipos activos: {equipos_validos} | Potencia total: {potencia_total:,.0f} W | Consumo diario: {consumo_total:,.0f} Wh/dia"
        ).replace(",", ".")
        actualizar_recomendacion()
        actualizar_resumen_economico()

    def actualizar_resumen_baterias(_=None):
        try:
            voltaje = a_float(bat_voltaje.value, "voltaje bateria")
            amperaje = a_float(bat_amperaje.value, "amperaje bateria")
            cantidad = a_float(bat_cantidad.value, "cantidad baterias")
        except ValueError:
            resumen_baterias.value = "Capacidad nominal por bateria: 0 Wh | Banco total: 0 kWh"
            actualizar_recomendacion()
            actualizar_resumen_economico()
            return
        capacidad_wh = voltaje * amperaje
        capacidad_total_kwh = (capacidad_wh * cantidad) / 1000.0
        resumen_baterias.value = (
            f"Capacidad nominal por bateria: {capacidad_wh:,.0f} Wh | Banco total: {capacidad_total_kwh:,.2f} kWh"
        ).replace(",", ".")
        actualizar_recomendacion()
        actualizar_resumen_economico()

    def actualizar_resumen_costos(_=None):
        total_costos = 0.0
        for fila in costos_filas:
            nombre_costo = fila["nombre"].value.strip()
            if not nombre_costo:
                fila["total"].value = "Total: $ 0"
                continue
            try:
                cantidad = a_float(fila["cantidad"].value, f"cantidad {nombre_costo}")
                precio = a_float(fila["precio"].value, f"precio {nombre_costo}")
                total_fila = cantidad * precio
                fila["total"].value = f"Total: {clp(total_fila)}"
                total_costos += total_fila
            except ValueError:
                fila["total"].value = "Total: $ 0"
        resumen_costos.value = f"Costos adicionales: {clp(total_costos)}"
        actualizar_resumen_economico()

    def crear_fila_equipo(data: Dict | None = None):
        nombre_inicial = (data or {}).get("nombre", "Refrigerador eficiente")
        potencia_inicial = (data or {}).get("potencia_w", CATALOGO_EQUIPOS_W.get(nombre_inicial, 0))
        cantidad_inicial = (data or {}).get("cantidad", 1)
        horas_inicial = (data or {}).get("horas_uso", 4)
        seleccion_inicial = nombre_inicial if nombre_inicial in CATALOGO_EQUIPOS_W else "Personalizado"

        selector = ft.Dropdown(label="Equipo", value=seleccion_inicial, options=opciones_equipo(), bgcolor=PALETA["superficie"], border_radius=12)
        nombre_equipo = ft.TextField(label="Nombre", value=nombre_inicial, bgcolor=PALETA["superficie"], border_radius=12)
        potencia = ft.TextField(label="Potencia (W)", value=str(potencia_inicial), bgcolor=PALETA["superficie"], border_radius=12)
        cantidad = ft.TextField(label="Cantidad", value=str(cantidad_inicial), bgcolor=PALETA["superficie"], border_radius=12)
        horas = ft.TextField(label="Hrs/dia", value=str(horas_inicial), bgcolor=PALETA["superficie"], border_radius=12)

        fila = {"selector": selector, "nombre": nombre_equipo, "potencia": potencia, "cantidad": cantidad, "horas": horas, "contenedor": None}

        def sincronizar_selector(_):
            if selector.value and selector.value != "Personalizado":
                nombre_equipo.value = selector.value
                potencia.value = str(CATALOGO_EQUIPOS_W[selector.value])
            actualizar_resumen_equipos()

        def eliminar_fila(_):
            if len(equipos_filas) == 1:
                notificar("Debe existir al menos un equipo", ok=False)
                return
            equipos_filas.remove(fila)
            equipos_lista.controls.remove(fila["contenedor"])
            actualizar_resumen_equipos()
            page.update()

        selector.on_change = sincronizar_selector
        nombre_equipo.on_change = actualizar_resumen_equipos
        potencia.on_change = actualizar_resumen_equipos
        cantidad.on_change = actualizar_resumen_equipos
        horas.on_change = actualizar_resumen_equipos

        fila["contenedor"] = ft.Container(
            bgcolor=PALETA["tarjeta"],
            border=borde_completo(PALETA["borde"]),
            border_radius=14,
            padding=12,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Equipo", weight=ft.FontWeight.W_600, color=PALETA["texto"]),
                            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=PALETA["secundario"], on_click=eliminar_fila),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Container(selector, col={"xs": 12, "md": 4}),
                            ft.Container(nombre_equipo, col={"xs": 12, "md": 4}),
                            ft.Container(potencia, col={"xs": 12, "md": 4}),
                            ft.Container(cantidad, col={"xs": 12, "md": 4}),
                            ft.Container(horas, col={"xs": 12, "md": 4}),
                        ]
                    ),
                ],
                spacing=8,
            ),
        )
        equipos_filas.append(fila)
        equipos_lista.controls.append(fila["contenedor"])

    def crear_fila_costo(data: Dict | None = None):
        nombre_inicial = (data or {}).get("nombre", "")
        cantidad_inicial = (data or {}).get("cantidad", 1)
        unidad_inicial = (data or {}).get("unidad", "unidad")
        precio_inicial = (data or {}).get("precio", (data or {}).get("valor", ""))

        nombre_costo = ft.TextField(label="Nombre", value=str(nombre_inicial), bgcolor=PALETA["superficie"], border_radius=12)
        cantidad = ft.TextField(label="Cantidad", value=str(cantidad_inicial), bgcolor=PALETA["superficie"], border_radius=12)
        unidad = ft.TextField(label="Unidad", value=str(unidad_inicial), bgcolor=PALETA["superficie"], border_radius=12)
        precio = ft.TextField(label="Precio unitario", value=str(precio_inicial), bgcolor=PALETA["superficie"], border_radius=12)
        total = ft.Text("Total: $ 0", color=PALETA["texto"])

        fila = {"nombre": nombre_costo, "cantidad": cantidad, "unidad": unidad, "precio": precio, "total": total, "contenedor": None}

        def eliminar_costo(_):
            costos_filas.remove(fila)
            costos_lista.controls.remove(fila["contenedor"])
            actualizar_resumen_costos()
            page.update()

        nombre_costo.on_change = actualizar_resumen_costos
        cantidad.on_change = actualizar_resumen_costos
        unidad.on_change = actualizar_resumen_costos
        precio.on_change = actualizar_resumen_costos

        fila["contenedor"] = ft.Container(
            bgcolor=PALETA["tarjeta"],
            border=borde_completo(PALETA["borde"]),
            border_radius=14,
            padding=12,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Costo adicional", weight=ft.FontWeight.W_600, color=PALETA["texto"]),
                            ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=PALETA["secundario"], on_click=eliminar_costo),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Container(nombre_costo, col={"xs": 12, "md": 4}),
                            ft.Container(cantidad, col={"xs": 12, "md": 2}),
                            ft.Container(unidad, col={"xs": 12, "md": 2}),
                            ft.Container(precio, col={"xs": 12, "md": 4}),
                        ]
                    ),
                    total,
                ],
                spacing=8,
            ),
        )
        costos_filas.append(fila)
        costos_lista.controls.append(fila["contenedor"])
        actualizar_resumen_costos()

    def limpiar_filas():
        equipos_filas.clear()
        costos_filas.clear()
        equipos_lista.controls.clear()
        costos_lista.controls.clear()

    def aplicar_payload(payload: Dict):
        nombre.value = payload.get("datos_cliente", {}).get("nombre", "")
        ciudad.value = payload.get("datos_cliente", {}).get("ciudad", "")
        email.value = payload.get("datos_cliente", {}).get("email", "")
        telefono.value = payload.get("datos_cliente", {}).get("telefono", "")

        empresa = {**EMPRESA_DEFAULT, **payload.get("empresa", {})}
        empresa_nombre.value = empresa.get("nombre", "")
        empresa_tagline.value = empresa.get("tagline", "")
        empresa_telefono.value = empresa.get("telefono", "")
        empresa_email.value = empresa.get("email", "")
        empresa_direccion.value = empresa.get("direccion", "")
        empresa_asesor.value = empresa.get("asesor", "")

        paneles = payload.get("paneles", {})
        panel_modelo.value = str(paneles.get("modelo", ""))
        panel_potencia.value = str(paneles.get("potencia_w", ""))
        panel_cantidad.value = str(paneles.get("cantidad", ""))
        panel_precio.value = str(paneles.get("precio", ""))

        inversor = payload.get("inversor", {})
        inv_modelo.value = str(inversor.get("modelo", ""))
        inv_potencia.value = str(inversor.get("potencia_w", ""))
        inv_cantidad.value = str(inversor.get("cantidad", ""))
        inv_precio.value = str(inversor.get("precio", ""))

        bateria = payload.get("bateria", {})
        bat_modelo.value = str(bateria.get("modelo", ""))
        bat_voltaje.value = str(bateria.get("voltaje_v", 48 if bateria.get("capacidad_kwh") else ""))
        if bateria.get("amperaje_ah") is not None:
            bat_amperaje.value = str(bateria.get("amperaje_ah", ""))
        elif bateria.get("capacidad_kwh") is not None and a_float_opcional(bat_voltaje.value) > 0:
            bat_amperaje.value = str((float(bateria.get("capacidad_kwh", 0)) * 1000.0) / a_float_opcional(bat_voltaje.value))
        else:
            bat_amperaje.value = ""
        bat_cantidad.value = str(bateria.get("cantidad", ""))
        bat_precio.value = str(bateria.get("precio", ""))

        parametros = payload.get("parametros_dimensionamiento", {})
        horas_solar_pico.value = str(parametros.get("horas_solar_pico", 5))
        autonomia_dias.value = str(parametros.get("autonomia_dias", 1))
        profundidad_descarga.value = str((parametros.get("profundidad_descarga", 0.8)) * 100)
        eficiencia_sistema.value = str((parametros.get("eficiencia_sistema", 0.85)) * 100)
        margen_seguridad.value = str((parametros.get("margen_seguridad", 1.2)) * 100)

        condiciones = {**CONDICIONES_DEFAULT, **payload.get("condiciones", {})}
        vigencia_dias.value = str(condiciones.get("vigencia_dias", 15))
        plazo_instalacion.value = condiciones.get("plazo_instalacion", "")
        garantia.value = condiciones.get("garantia", "")
        observaciones.value = condiciones.get("observaciones", "")
        iva.value = str(payload.get("porcentaje_iva", 19))

        limpiar_filas()
        for equipo in payload.get("equipos_uso", []):
            crear_fila_equipo(equipo)
        if not payload.get("equipos_uso"):
            crear_fila_equipo()

        costos_payload = payload.get("costos_adicionales", [])
        if not costos_payload:
            costos_payload = []
            cable_metros = payload.get("cable_metros", 0)
            precio_cable = payload.get("precio_cable_metro", 0)
            mano_obra = payload.get("mano_obra", 0)
            if cable_metros and precio_cable:
                costos_payload.append({"nombre": "Cable solar especializado DC/AC", "cantidad": cable_metros, "unidad": "m", "precio": precio_cable})
            if mano_obra:
                costos_payload.append({"nombre": "Instalacion y puesta en marcha", "cantidad": 1, "unidad": "servicio", "precio": mano_obra})
        for costo in costos_payload:
            crear_fila_costo(costo)

        actualizar_resumen_baterias()
        actualizar_resumen_equipos()
        actualizar_resumen_costos()

    def cargar_historial(_=None):
        historial.options = []
        for item in listar_cotizaciones(filtro=filtro_historial.value):
            etiqueta = f"#{item['id']} | {item['fecha']} | {item['cliente']} | {clp(item['total'])}"
            historial.options.append(ft.dropdown.Option(key=str(item["id"]), text=etiqueta))
        page.update()

    def aplicar_recomendacion_click(_):
        recomendacion = recomendacion_cache.get("valor")
        if not recomendacion:
            notificar("No hay recomendacion disponible", ok=False)
            return
        panel_cantidad.value = str(recomendacion["paneles_recomendados"])
        inv_cantidad.value = str(recomendacion["inversores_recomendados"])
        bat_cantidad.value = str(recomendacion["baterias_recomendadas"])
        actualizar_resumen_baterias()
        actualizar_resumen_equipos()
        notificar("Cantidades aplicadas segun recomendacion automatica")

    def cargar_plantilla_click(_):
        plantilla = PLANTILLAS.get(selector_plantilla.value)
        if not plantilla:
            notificar("Selecciona una plantilla valida", ok=False)
            return
        equipos_filas.clear()
        equipos_lista.controls.clear()
        for equipo in plantilla:
            crear_fila_equipo(equipo)
        actualizar_resumen_equipos()
        page.update()

    def generar_click(_):
        try:
            payload = construir_payload()
            recomendacion = recomendacion_cache.get("valor") or calcular_dimensionamiento(
                payload["equipos_uso"],
                payload["paneles"],
                payload["inversor"],
                payload["bateria"],
                **payload["parametros_dimensionamiento"],
            )
            resultado = generar_presupuesto(
                datos_cliente=payload["datos_cliente"],
                paneles=payload["paneles"],
                inversor=payload["inversor"],
                bateria=payload["bateria"],
                equipos_uso=payload["equipos_uso"],
                costos_adicionales=payload["costos_adicionales"],
                porcentaje_iva=payload["porcentaje_iva"],
                empresa=payload["empresa"],
                condiciones=payload["condiciones"],
                recomendacion=recomendacion,
            )
            ruta_pdf = os.path.abspath(resultado["archivo"])
            estado["archivo"] = ruta_pdf
            estado["total"] = float(resultado["total"])
            cotizacion_id = guardar_cotizacion(payload, resultado["total"], ruta_pdf)
            estado["cotizacion_id"] = cotizacion_id
            salida.value = (
                f"Cotizacion #{cotizacion_id}\n"
                f"Archivo: {ruta_pdf}\n"
                f"Consumo diario: {resultado['consumo_diario_wh']:.0f} Wh/dia\n"
                f"Potencia instantanea: {resultado['potencia_instantanea_w']:.0f} W\n"
                f"Total proforma: {clp(resultado['total'])}"
            )
            cargar_historial()
            notificar("Proforma generada correctamente")
        except Exception as exc:
            salida.value = ""
            notificar(str(exc), ok=False)

    def abrir_pdf_click(_):
        if not estado["archivo"]:
            notificar("Primero genera la proforma", ok=False)
            return
        page.launch_url("file:///" + estado["archivo"].replace("\\", "/"))

    def cargar_desde_historial_click(_):
        if not historial.value:
            notificar("Selecciona una cotizacion del historial", ok=False)
            return
        try:
            payload = obtener_cotizacion(int(historial.value))
            aplicar_payload(payload)
            estado["archivo"] = payload.get("pdf_path", "")
            estado["cotizacion_id"] = int(historial.value)
            notificar("Cotizacion cargada correctamente")
        except Exception as exc:
            notificar(str(exc), ok=False)

    def compartir_whatsapp_click(_):
        if not estado["archivo"]:
            notificar("Primero genera la proforma", ok=False)
            return
        mensaje = (
            f"Hola, te comparto la proforma solar. "
            f"Total estimado: {clp(estado['total'])}. "
            f"Archivo generado en: {estado['archivo']}"
        )
        page.launch_url(f"https://wa.me/?text={quote(mensaje)}")

    def compartir_email_click(_):
        if not estado["archivo"]:
            notificar("Primero genera la proforma", ok=False)
            return
        asunto = quote("Proforma sistema fotovoltaico")
        cuerpo = quote(
            "Adjunto la proforma generada. "
            f"Total estimado: {clp(estado['total'])}. "
            f"Ruta del archivo: {estado['archivo']}"
        )
        page.launch_url(f"mailto:?subject={asunto}&body={cuerpo}")

    btn_generar = ft.FilledButton("Generar PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=generar_click, style=estilo_boton_primario())
    btn_abrir = ft.OutlinedButton("Abrir PDF", icon=ft.Icons.OPEN_IN_NEW, on_click=abrir_pdf_click, style=estilo_boton_secundario())
    btn_cargar = ft.OutlinedButton("Cargar historial", icon=ft.Icons.HISTORY, on_click=cargar_desde_historial_click, style=estilo_boton_secundario())
    btn_whatsapp = ft.OutlinedButton("WhatsApp", icon=ft.Icons.SEND, on_click=compartir_whatsapp_click, style=estilo_boton_secundario())
    btn_email = ft.OutlinedButton("Email", icon=ft.Icons.MAIL_OUTLINE, on_click=compartir_email_click, style=estilo_boton_secundario())
    btn_aplicar = ft.OutlinedButton("Aplicar recomendacion", icon=ft.Icons.AUTO_FIX_HIGH, on_click=aplicar_recomendacion_click, style=estilo_boton_secundario())
    btn_agregar_equipo = ft.OutlinedButton("Agregar equipo", icon=ft.Icons.ADD, on_click=lambda _: (crear_fila_equipo(), actualizar_resumen_equipos(), page.update()), style=estilo_boton_secundario())
    btn_agregar_costo = ft.OutlinedButton("Agregar costo", icon=ft.Icons.ADD, on_click=lambda _: (crear_fila_costo(), actualizar_resumen_costos(), page.update()), style=estilo_boton_secundario())
    btn_plantilla = ft.OutlinedButton("Cargar plantilla", icon=ft.Icons.DATA_OBJECT, on_click=cargar_plantilla_click, style=estilo_boton_secundario())

    def recalcular_componentes(_=None):
        actualizar_resumen_baterias()
        actualizar_resumen_equipos()

    for campo in [
        panel_potencia,
        panel_cantidad,
        panel_precio,
        inv_potencia,
        inv_cantidad,
        inv_precio,
        bat_voltaje,
        bat_amperaje,
        bat_cantidad,
        bat_precio,
        horas_solar_pico,
        autonomia_dias,
        profundidad_descarga,
        eficiencia_sistema,
        margen_seguridad,
        iva,
    ]:
        campo.on_change = recalcular_componentes

    filtro_historial.on_change = cargar_historial

    crear_fila_equipo()
    crear_fila_costo({"nombre": "Instalacion", "cantidad": 1, "unidad": "servicio", "precio": 600000})
    actualizar_resumen_baterias()
    actualizar_resumen_equipos()
    actualizar_resumen_costos()
    cargar_historial()

    logo_control = ft.Container(
        content=ft.Image(src=LOGO_PATH, fit="contain", height=88) if os.path.exists(LOGO_PATH) else ft.Text(
            EMPRESA_DEFAULT["nombre"],
            size=30,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        ),
        alignment=ft.Alignment(-1, 0),
    )

    resumen_superior = ft.Container(
        bgcolor=PALETA["primario"],
        border_radius=20,
        padding=20,
        content=ft.Column(
            [
                logo_control,
                ft.Text(
                    "Cotizaciones fotovoltaicas con recomendacion automatica y proforma PDF comercial",
                    size=14,
                    color=ft.Colors.BLUE_GREY_100,
                ),
            ],
            spacing=6,
        ),
    )

    card_demanda = tarjeta_seccion(
        "Demanda de equipos",
        "Primero define consumos y revisa potencia total antes de escoger componentes.",
        ft.Column(
            [
                ft.Container(bgcolor=PALETA["superficie"], border_radius=14, padding=12, content=resumen_demanda),
                ft.ResponsiveRow([
                    ft.Container(selector_plantilla, col={"xs": 12, "md": 8}),
                    ft.Container(btn_plantilla, col={"xs": 12, "md": 4}),
                ]),
                btn_agregar_equipo,
                equipos_lista,
            ],
            spacing=10,
        ),
    )

    card_recomendacion = tarjeta_seccion(
        "Dimensionamiento automatico",
        "La app recomienda cantidades segun demanda, autonomia y rendimiento del sistema.",
        ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(horas_solar_pico, col={"xs": 12, "md": 3}),
                        ft.Container(autonomia_dias, col={"xs": 12, "md": 3}),
                        ft.Container(profundidad_descarga, col={"xs": 12, "md": 2}),
                        ft.Container(eficiencia_sistema, col={"xs": 12, "md": 2}),
                        ft.Container(margen_seguridad, col={"xs": 12, "md": 2}),
                    ]
                ),
                ft.Container(bgcolor=PALETA["superficie"], border_radius=14, padding=12, content=resumen_recomendacion),
                btn_aplicar,
            ],
            spacing=10,
        ),
    )

    card_cliente = tarjeta_seccion(
        "Cliente y empresa",
        "Configura datos de la proforma y branding comercial del PDF.",
        ft.Column(
            [
                nombre,
                ciudad,
                email,
                telefono,
                ft.Divider(color=PALETA["borde"]),
                empresa_nombre,
                empresa_tagline,
                ft.ResponsiveRow(
                    [
                        ft.Container(empresa_telefono, col={"xs": 12, "md": 4}),
                        ft.Container(empresa_email, col={"xs": 12, "md": 4}),
                        ft.Container(empresa_asesor, col={"xs": 12, "md": 4}),
                    ]
                ),
                empresa_direccion,
            ],
            spacing=10,
        ),
    )

    card_paneles = tarjeta_seccion(
        "Paneles",
        "Define modelo, potencia, cantidad y precio unitario.",
        ft.Column(
            [
                panel_modelo,
                ft.ResponsiveRow(
                    [
                        ft.Container(panel_potencia, col={"xs": 12, "md": 4}),
                        ft.Container(panel_cantidad, col={"xs": 12, "md": 4}),
                        ft.Container(panel_precio, col={"xs": 12, "md": 4}),
                    ]
                ),
            ],
            spacing=10,
        ),
    )

    card_inversor = tarjeta_seccion(
        "Inversor",
        "Configura la capacidad del inversor y su valor.",
        ft.Column(
            [
                inv_modelo,
                ft.ResponsiveRow(
                    [
                        ft.Container(inv_potencia, col={"xs": 12, "md": 4}),
                        ft.Container(inv_cantidad, col={"xs": 12, "md": 4}),
                        ft.Container(inv_precio, col={"xs": 12, "md": 4}),
                    ]
                ),
            ],
            spacing=10,
        ),
    )

    card_baterias = tarjeta_seccion(
        "Baterias",
        "Ingresa voltaje y amperaje; la app calcula la capacidad del banco.",
        ft.Column(
            [
                bat_modelo,
                ft.ResponsiveRow(
                    [
                        ft.Container(bat_voltaje, col={"xs": 12, "md": 3}),
                        ft.Container(bat_amperaje, col={"xs": 12, "md": 3}),
                        ft.Container(bat_cantidad, col={"xs": 12, "md": 3}),
                        ft.Container(bat_precio, col={"xs": 12, "md": 3}),
                    ]
                ),
                ft.Container(bgcolor=PALETA["superficie"], border_radius=14, padding=12, content=resumen_baterias),
            ],
            spacing=10,
        ),
    )

    card_costos = tarjeta_seccion(
        "Costos adicionales",
        "Agrega cantidad, unidad y precio unitario para cada item extra.",
        ft.Column(
            [
                ft.Container(bgcolor=PALETA["superficie"], border_radius=14, padding=12, content=resumen_costos),
                btn_agregar_costo,
                costos_lista,
                iva,
                ft.Container(bgcolor=PALETA["superficie"], border_radius=14, padding=12, content=resumen_economico),
            ],
            spacing=10,
        ),
    )

    card_condiciones = tarjeta_seccion(
        "Condiciones comerciales",
        "Estos textos se imprimen en el PDF para dar mejor presentacion al cliente.",
        ft.Column([vigencia_dias, plazo_instalacion, garantia, observaciones], spacing=10),
    )

    card_acciones = tarjeta_seccion(
        "Acciones e historial",
        "Genera, recupera y comparte proformas desde la misma app.",
        ft.Column(
            [
                filtro_historial,
                historial,
                ft.Row([btn_cargar, btn_generar, btn_abrir], wrap=True),
                ft.Row([btn_whatsapp, btn_email], wrap=True),
                ft.Container(bgcolor=PALETA["superficie"], border_radius=14, padding=12, content=salida),
            ],
            spacing=10,
        ),
    )

    page.add(
        ft.Column(
            [
                resumen_superior,
                card_demanda,
                card_recomendacion,
                card_cliente,
                card_paneles,
                card_inversor,
                card_baterias,
                card_costos,
                card_condiciones,
                card_acciones,
            ],
            spacing=16,
            width=780,
        )
    )


if __name__ == "__main__":
    ft.run(construir_ui)
