from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Dict, List, Optional

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent


def resolver_logo_default() -> Path:
    for nombre in ["logo_sm_spa.png", "logo_sm_spa.jpg", "logo_sm_spa.jpeg", "logo_sm_spa.svg"]:
        ruta = BASE_DIR / "assets" / nombre
        if ruta.exists():
            return ruta
    return BASE_DIR / "assets" / "logo_sm_spa.svg"


DEFAULT_LOGO_PATH = resolver_logo_default()


CATALOGO_EQUIPOS_W = {
    "Refrigerador eficiente": 150,
    "Televisor LED 50\"": 120,
    "Router": 12,
    "Iluminacion LED (por foco)": 12,
    "Lavadora": 600,
    "Microondas": 1200,
    "Bomba de agua 1HP": 746,
    "Aire acondicionado 9000 BTU": 900,
}

EMPRESA_DEFAULT = {
    "nombre": "S&M SpA",
    "tagline": "Venta e instalacion de sistemas fotovoltaicos",
    "telefono": "",
    "email": "",
    "direccion": "",
    "asesor": "",
    "logo_path": str(DEFAULT_LOGO_PATH) if DEFAULT_LOGO_PATH.exists() else "",
}

CONDICIONES_DEFAULT = {
    "vigencia_dias": 15,
    "plazo_instalacion": "5 a 10 dias habiles",
    "garantia": "12 meses sobre instalacion y garantia de fabricante en equipos",
    "observaciones": "La propuesta puede ajustarse despues de la visita tecnica definitiva.",
}


class ProformaSolar(FPDF):
    def __init__(self, empresa: Optional[Dict] = None):
        super().__init__()
        self.empresa = {**EMPRESA_DEFAULT, **(empresa or {})}

    def header(self):
        logo_path = self.empresa.get("logo_path") or ""
        if logo_path and Path(logo_path).exists():
            try:
                self.image(logo_path, x=10, y=8, w=42)
            except Exception:
                logo_path = ""

        self.set_fill_color(71, 85, 105)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 16)
        if logo_path:
            self.cell(46, 10, "", fill=True)
            self.cell(0, 10, self.empresa["nombre"], ln=True, fill=True)
        else:
            self.cell(0, 10, self.empresa["nombre"], ln=True, fill=True)
        self.set_font("Arial", "", 10)
        if logo_path:
            self.cell(46, 6, "", fill=True)
            self.cell(0, 6, self.empresa.get("tagline", "Proforma solar"), ln=True, fill=True)
        else:
            self.cell(0, 6, self.empresa.get("tagline", "Proforma solar"), ln=True, fill=True)
        self.ln(4)
        self.set_text_color(17, 24, 39)
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, "PROFORMA DE SISTEMA FOTOVOLTAICO", ln=True)
        self.set_font("Arial", "", 10)
        self.cell(0, 5, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        contacto = " | ".join(
            [
                valor
                for valor in [
                    self.empresa.get("telefono"),
                    self.empresa.get("email"),
                    self.empresa.get("direccion"),
                ]
                if valor
            ]
        )
        if contacto:
            self.cell(0, 5, contacto, ln=True)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", align="C")


def clp(valor: float) -> str:
    return f"$ {valor:,.0f}".replace(",", ".")


def validar_numero_no_negativo(valor: float, campo: str):
    if valor < 0:
        raise ValueError(f"El campo '{campo}' no puede ser negativo")


def sanitizar_nombre_archivo(nombre: str) -> str:
    permitido = [
        caracter if caracter.isalnum() or caracter in {"-", "_"} else "_"
        for caracter in nombre.strip().replace(" ", "_")
    ]
    nombre_limpio = "".join(permitido).strip("_")
    return nombre_limpio or "cliente"


def calcular_capacidad_bateria_kwh(bateria: Dict) -> float:
    capacidad_kwh = bateria.get("capacidad_kwh")
    if capacidad_kwh is not None:
        validar_numero_no_negativo(float(capacidad_kwh), "capacidad_kwh")
        return float(capacidad_kwh)

    voltaje_v = bateria.get("voltaje_v")
    amperaje_ah = bateria.get("amperaje_ah")
    if voltaje_v is None or amperaje_ah is None:
        raise ValueError("La bateria debe incluir capacidad_kwh o voltaje_v y amperaje_ah")

    validar_numero_no_negativo(float(voltaje_v), "voltaje_v")
    validar_numero_no_negativo(float(amperaje_ah), "amperaje_ah")
    return (float(voltaje_v) * float(amperaje_ah)) / 1000.0


def calcular_potencia_bateria_nominal(bateria: Dict) -> Optional[float]:
    voltaje_v = bateria.get("voltaje_v")
    amperaje_ah = bateria.get("amperaje_ah")
    if voltaje_v is None or amperaje_ah is None:
        return None
    validar_numero_no_negativo(float(voltaje_v), "voltaje_v")
    validar_numero_no_negativo(float(amperaje_ah), "amperaje_ah")
    return float(voltaje_v) * float(amperaje_ah)


def calcular_consumo_diario_wh(equipos_uso: List[Dict]) -> float:
    total_wh = 0.0
    for equipo in equipos_uso:
        nombre = equipo["nombre"]
        cantidad = float(equipo.get("cantidad", 0))
        horas_uso = float(equipo.get("horas_uso", 0))
        validar_numero_no_negativo(cantidad, f"cantidad {nombre}")
        validar_numero_no_negativo(horas_uso, f"horas_uso {nombre}")

        potencia_w = equipo.get("potencia_w")
        if potencia_w is None:
            potencia_w = CATALOGO_EQUIPOS_W.get(nombre)
        if potencia_w is None:
            raise ValueError(f"No existe potencia predefinida para '{nombre}'")

        total_wh += float(potencia_w) * cantidad * horas_uso
    return total_wh


def calcular_potencia_instantanea_w(equipos_uso: List[Dict]) -> float:
    total_w = 0.0
    for equipo in equipos_uso:
        nombre = equipo["nombre"]
        cantidad = float(equipo.get("cantidad", 0))
        validar_numero_no_negativo(cantidad, f"cantidad {nombre}")

        potencia_w = equipo.get("potencia_w")
        if potencia_w is None:
            potencia_w = CATALOGO_EQUIPOS_W.get(nombre)
        if potencia_w is None:
            raise ValueError(f"No existe potencia predefinida para '{nombre}'")

        total_w += float(potencia_w) * cantidad
    return total_w


def normalizar_costos_adicionales(
    costos_adicionales: Optional[List[Dict]],
    cable_metros: float = 0.0,
    precio_cable_metro: float = 0.0,
    mano_obra: float = 0.0,
) -> List[Dict]:
    validar_numero_no_negativo(float(cable_metros), "cable_metros")
    validar_numero_no_negativo(float(precio_cable_metro), "precio_cable_metro")
    validar_numero_no_negativo(float(mano_obra), "mano_obra")

    if costos_adicionales is None:
        costos_adicionales = []
        if cable_metros > 0 and precio_cable_metro > 0:
            costos_adicionales.append(
                {
                    "nombre": "Cable solar especializado DC/AC",
                    "cantidad": float(cable_metros),
                    "precio": float(precio_cable_metro),
                    "unidad": "m",
                }
            )
        if mano_obra > 0:
            costos_adicionales.append(
                {
                    "nombre": "Instalacion y puesta en marcha",
                    "cantidad": 1.0,
                    "precio": float(mano_obra),
                    "unidad": "servicio",
                }
            )

    costos_normalizados = []
    for costo in costos_adicionales:
        nombre = str(costo.get("nombre", "Costo adicional")).strip() or "Costo adicional"
        cantidad = float(costo.get("cantidad", 1.0))
        precio = float(costo.get("precio", 0.0))
        unidad = str(costo.get("unidad", "")).strip()
        validar_numero_no_negativo(cantidad, f"cantidad {nombre}")
        validar_numero_no_negativo(precio, f"precio {nombre}")
        costos_normalizados.append(
            {"nombre": nombre, "cantidad": cantidad, "precio": precio, "unidad": unidad}
        )
    return costos_normalizados


def construir_items_costeo(
    paneles: Dict,
    inversor: Dict,
    bateria: Dict,
    costos_adicionales: Optional[List[Dict]] = None,
) -> List[Dict]:
    capacidad_bateria_kwh = calcular_capacidad_bateria_kwh(bateria)
    items = [
        {
            "nombre": f"Panel solar {paneles['modelo']} ({float(paneles['potencia_w']):,.0f}W)".replace(",", "."),
            "cantidad": float(paneles["cantidad"]),
            "precio": float(paneles["precio"]),
            "unidad": "unidad",
        },
        {
            "nombre": f"Inversor {inversor['modelo']} ({float(inversor['potencia_w']):,.0f}W)".replace(",", "."),
            "cantidad": float(inversor["cantidad"]),
            "precio": float(inversor["precio"]),
            "unidad": "unidad",
        },
        {
            "nombre": f"Bateria {bateria['modelo']} ({capacidad_bateria_kwh:.2f}kWh)",
            "cantidad": float(bateria["cantidad"]),
            "precio": float(bateria["precio"]),
            "unidad": "unidad",
        },
    ]
    for item in items:
        validar_numero_no_negativo(item["cantidad"], f"cantidad {item['nombre']}")
        validar_numero_no_negativo(item["precio"], f"precio {item['nombre']}")
    return items + normalizar_costos_adicionales(costos_adicionales)


def calcular_totales_cotizacion(
    paneles: Dict,
    inversor: Dict,
    bateria: Dict,
    costos_adicionales: Optional[List[Dict]] = None,
    porcentaje_iva: float = 19.0,
) -> Dict:
    validar_numero_no_negativo(float(porcentaje_iva), "porcentaje_iva")
    items = construir_items_costeo(paneles, inversor, bateria, costos_adicionales)
    subtotal = 0.0
    for item in items:
        subtotal += float(item["cantidad"]) * float(item["precio"])
    iva = subtotal * (float(porcentaje_iva) / 100.0)
    total = subtotal + iva
    return {"items": items, "subtotal": subtotal, "iva": iva, "total": total}


def calcular_dimensionamiento(
    equipos_uso: List[Dict],
    paneles: Dict,
    inversor: Dict,
    bateria: Dict,
    horas_solar_pico: float = 5.0,
    autonomia_dias: float = 1.0,
    profundidad_descarga: float = 0.8,
    eficiencia_sistema: float = 0.85,
    margen_seguridad: float = 1.2,
) -> Dict:
    if horas_solar_pico <= 0:
        raise ValueError("Las horas solares pico deben ser mayores que 0")
    if autonomia_dias <= 0:
        raise ValueError("La autonomia debe ser mayor que 0")
    if profundidad_descarga <= 0 or profundidad_descarga > 1:
        raise ValueError("La profundidad de descarga debe estar entre 0 y 1")
    if eficiencia_sistema <= 0 or eficiencia_sistema > 1:
        raise ValueError("La eficiencia del sistema debe estar entre 0 y 1")
    if margen_seguridad < 1:
        raise ValueError("El margen de seguridad debe ser mayor o igual a 1")

    consumo_diario_wh = calcular_consumo_diario_wh(equipos_uso)
    potencia_instantanea_w = calcular_potencia_instantanea_w(equipos_uso)
    potencia_panel_unitaria = float(paneles["potencia_w"])
    potencia_inversor_unidad = float(inversor["potencia_w"])
    capacidad_bateria_unitaria_wh = calcular_capacidad_bateria_kwh(bateria) * 1000.0

    validar_numero_no_negativo(potencia_panel_unitaria, "potencia panel")
    validar_numero_no_negativo(potencia_inversor_unidad, "potencia inversor")
    validar_numero_no_negativo(capacidad_bateria_unitaria_wh, "capacidad bateria")

    energia_requerida_paneles = consumo_diario_wh * margen_seguridad / eficiencia_sistema
    energia_respaldo_baterias = consumo_diario_wh * autonomia_dias * margen_seguridad
    potencia_pico_recomendada = potencia_instantanea_w * margen_seguridad

    paneles_recomendados = max(1, ceil(energia_requerida_paneles / (potencia_panel_unitaria * horas_solar_pico)))
    inversores_recomendados = max(1, ceil(potencia_pico_recomendada / potencia_inversor_unidad))
    baterias_recomendadas = max(
        1, ceil(energia_respaldo_baterias / (capacidad_bateria_unitaria_wh * profundidad_descarga))
    )

    paneles_actuales = float(paneles.get("cantidad", 0))
    inversores_actuales = float(inversor.get("cantidad", 0))
    baterias_actuales = float(bateria.get("cantidad", 0))

    return {
        "consumo_diario_wh": consumo_diario_wh,
        "potencia_instantanea_w": potencia_instantanea_w,
        "paneles_recomendados": paneles_recomendados,
        "inversores_recomendados": inversores_recomendados,
        "baterias_recomendadas": baterias_recomendadas,
        "paneles_actuales": paneles_actuales,
        "inversores_actuales": inversores_actuales,
        "baterias_actuales": baterias_actuales,
        "paneles_cubren": paneles_actuales >= paneles_recomendados,
        "inversores_cubren": inversores_actuales >= inversores_recomendados,
        "baterias_cubren": baterias_actuales >= baterias_recomendadas,
        "horas_solar_pico": horas_solar_pico,
        "autonomia_dias": autonomia_dias,
        "profundidad_descarga": profundidad_descarga,
        "eficiencia_sistema": eficiencia_sistema,
        "margen_seguridad": margen_seguridad,
        "potencia_panel_unitaria_w": potencia_panel_unitaria,
        "potencia_inversor_unidad_w": potencia_inversor_unidad,
        "capacidad_bateria_unitaria_wh": capacidad_bateria_unitaria_wh,
    }


def generar_presupuesto(
    datos_cliente: Dict,
    paneles: Dict,
    inversor: Dict,
    bateria: Dict,
    equipos_uso: List[Dict],
    cable_metros: float = 0.0,
    precio_cable_metro: float = 0.0,
    mano_obra: float = 0.0,
    costos_adicionales: Optional[List[Dict]] = None,
    porcentaje_iva: float = 19.0,
    empresa: Optional[Dict] = None,
    condiciones: Optional[Dict] = None,
    recomendacion: Optional[Dict] = None,
    directorio_salida: Optional[str] = None,
):
    empresa = {**EMPRESA_DEFAULT, **(empresa or {})}
    condiciones = {**CONDICIONES_DEFAULT, **(condiciones or {})}
    costos_normalizados = normalizar_costos_adicionales(
        costos_adicionales, cable_metros, precio_cable_metro, mano_obra
    )
    totales = calcular_totales_cotizacion(
        paneles, inversor, bateria, costos_normalizados, porcentaje_iva
    )

    capacidad_bateria_kwh = calcular_capacidad_bateria_kwh(bateria)
    potencia_bateria_nominal = calcular_potencia_bateria_nominal(bateria)
    consumo_diario_wh = calcular_consumo_diario_wh(equipos_uso)
    potencia_instantanea_w = calcular_potencia_instantanea_w(equipos_uso)
    potencia_paneles_w = float(paneles["cantidad"]) * float(paneles["potencia_w"])
    energia_bateria_kwh = float(bateria["cantidad"]) * capacidad_bateria_kwh

    if recomendacion is None:
        recomendacion = calcular_dimensionamiento(equipos_uso, paneles, inversor, bateria)

    pdf = ProformaSolar(empresa=empresa)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Datos del cliente", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"Nombre: {datos_cliente['nombre']}", ln=True)
    pdf.cell(0, 5, f"Ubicacion: {datos_cliente['ciudad']}", ln=True)
    if datos_cliente.get("email"):
        pdf.cell(0, 5, f"Email: {datos_cliente['email']}", ln=True)
    if datos_cliente.get("telefono"):
        pdf.cell(0, 5, f"Telefono: {datos_cliente['telefono']}", ln=True)
    if empresa.get("asesor"):
        pdf.cell(0, 5, f"Asesor comercial: {empresa['asesor']}", ln=True)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Resumen ejecutivo", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(
        0,
        5,
        (
            f"La presente proforma considera una demanda estimada de {potencia_instantanea_w:,.0f} W y un consumo diario de "
            f"{consumo_diario_wh:,.0f} Wh/dia. Se propone una configuracion con {int(float(paneles['cantidad']))} panel(es), "
            f"{int(float(inversor['cantidad']))} inversor(es) y {int(float(bateria['cantidad']))} bateria(s)."
        ).replace(",", "."),
    )
    pdf.ln(2)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Resumen tecnico", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"Potencia total en paneles: {potencia_paneles_w:,.0f} W".replace(",", "."), ln=True)
    pdf.cell(0, 5, f"Capacidad total en baterias: {energia_bateria_kwh:,.2f} kWh".replace(",", "."), ln=True)
    if bateria.get("voltaje_v") is not None and bateria.get("amperaje_ah") is not None:
        pdf.cell(
            0,
            5,
            (
                f"Bateria por unidad: {float(bateria['voltaje_v']):,.0f} V / "
                f"{float(bateria['amperaje_ah']):,.0f} Ah"
            ).replace(",", "."),
            ln=True,
        )
    if potencia_bateria_nominal is not None:
        pdf.cell(0, 5, f"Capacidad nominal por bateria: {potencia_bateria_nominal:,.0f} Wh".replace(",", "."), ln=True)
    pdf.cell(0, 5, f"Demanda instantanea estimada: {potencia_instantanea_w:,.0f} W".replace(",", "."), ln=True)
    pdf.cell(0, 5, f"Consumo diario estimado: {consumo_diario_wh:,.0f} Wh/dia".replace(",", "."), ln=True)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Recomendacion automatica", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"Paneles recomendados: {recomendacion['paneles_recomendados']} | Configurados: {int(recomendacion['paneles_actuales'])}", ln=True)
    pdf.cell(0, 5, f"Inversores recomendados: {recomendacion['inversores_recomendados']} | Configurados: {int(recomendacion['inversores_actuales'])}", ln=True)
    pdf.cell(0, 5, f"Baterias recomendadas: {recomendacion['baterias_recomendadas']} | Configuradas: {int(recomendacion['baterias_actuales'])}", ln=True)
    pdf.cell(
        0,
        5,
        f"Supuestos: HSP {recomendacion['horas_solar_pico']}, autonomia {recomendacion['autonomia_dias']} dia(s), DOD {recomendacion['profundidad_descarga'] * 100:.0f}%".replace(",", "."),
        ln=True,
    )
    pdf.ln(3)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Cargas declaradas", ln=True)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 7, "Equipo", border=1)
    pdf.cell(20, 7, "Cant.", border=1, align="C")
    pdf.cell(30, 7, "Potencia W", border=1, align="C")
    pdf.cell(25, 7, "Hrs/dia", border=1, align="C")
    pdf.cell(45, 7, "Consumo Wh/dia", border=1, align="R")
    pdf.ln()

    pdf.set_font("Arial", "", 9)
    for equipo in equipos_uso:
        potencia_w = equipo.get("potencia_w") or CATALOGO_EQUIPOS_W.get(equipo["nombre"])
        if potencia_w is None:
            raise ValueError(f"No existe potencia para '{equipo['nombre']}'")
        consumo_equipo = float(equipo["cantidad"]) * float(equipo["horas_uso"]) * float(potencia_w)
        pdf.cell(70, 7, equipo["nombre"], border=1)
        pdf.cell(20, 7, str(equipo["cantidad"]), border=1, align="C")
        pdf.cell(30, 7, f"{potencia_w}", border=1, align="C")
        pdf.cell(25, 7, f"{equipo['horas_uso']}", border=1, align="C")
        pdf.cell(45, 7, f"{consumo_equipo:,.0f}".replace(",", "."), border=1, align="R")
        pdf.ln()
    pdf.ln(3)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Detalle economico", ln=True)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(80, 7, "Descripcion", border=1)
    pdf.cell(25, 7, "Cant./Unidad", border=1, align="C")
    pdf.cell(40, 7, "Precio Unit.", border=1, align="C")
    pdf.cell(45, 7, "Total", border=1, align="C")
    pdf.ln()

    pdf.set_font("Arial", "", 10)
    for item in totales["items"]:
        total_item = float(item["cantidad"]) * float(item["precio"])
        cantidad_txt = f"{float(item['cantidad']):,.2f}".replace(",", ".")
        if item.get("unidad"):
            cantidad_txt = f"{cantidad_txt} {item['unidad']}"
        pdf.cell(80, 7, item["nombre"], border=1)
        pdf.cell(25, 7, cantidad_txt, border=1, align="C")
        pdf.cell(40, 7, clp(float(item["precio"])), border=1, align="R")
        pdf.cell(45, 7, clp(total_item), border=1, align="R")
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(145, 7, "Subtotal:", align="R")
    pdf.cell(45, 7, clp(totales["subtotal"]), border=1, align="R")
    pdf.ln()
    pdf.cell(145, 7, f"IVA ({float(porcentaje_iva):.0f}%):", align="R")
    pdf.cell(45, 7, clp(totales["iva"]), border=1, align="R")
    pdf.ln()
    pdf.cell(145, 8, "TOTAL PROFORMA:", align="R")
    pdf.cell(45, 8, clp(totales["total"]), border=1, align="R")
    pdf.ln(6)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, "Condiciones comerciales", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(
        0,
        5,
        (
            f"Vigencia de oferta: {condiciones['vigencia_dias']} dias.\n"
            f"Plazo estimado de instalacion: {condiciones['plazo_instalacion']}.\n"
            f"Garantia: {condiciones['garantia']}.\n"
            f"Observaciones: {condiciones['observaciones']}"
        ),
    )

    nombre_archivo = f"Proforma_{sanitizar_nombre_archivo(datos_cliente['nombre'])}.pdf"
    ruta_salida = Path(directorio_salida) / nombre_archivo if directorio_salida else Path(nombre_archivo)
    pdf.output(str(ruta_salida))

    return {
        "archivo": str(ruta_salida),
        "consumo_diario_wh": consumo_diario_wh,
        "potencia_instantanea_w": potencia_instantanea_w,
        "subtotal": totales["subtotal"],
        "iva": totales["iva"],
        "total": totales["total"],
        "recomendacion": recomendacion,
        "items": totales["items"],
    }


if __name__ == "__main__":
    cliente = {
        "nombre": "Juan Perez",
        "ciudad": "Calama",
        "email": "juan@email.com",
        "telefono": "+56 9 1234 5678",
    }
    paneles_cfg = {"modelo": "Monocristalino 550W", "potencia_w": 550, "cantidad": 8, "precio": 150000}
    inversor_cfg = {"modelo": "Hibrido 5kW", "potencia_w": 5000, "cantidad": 1, "precio": 1200000}
    bateria_cfg = {"modelo": "Litio 48V", "voltaje_v": 48, "amperaje_ah": 100, "cantidad": 2, "precio": 1800000}
    costos = [
        {"nombre": "Cable solar especializado DC/AC", "cantidad": 45, "precio": 2500, "unidad": "m"},
        {"nombre": "Instalacion y puesta en marcha", "cantidad": 1, "precio": 600000, "unidad": "servicio"},
    ]
    equipos = [
        {"nombre": "Refrigerador eficiente", "cantidad": 1, "horas_uso": 18},
        {"nombre": "Iluminacion LED (por foco)", "cantidad": 8, "horas_uso": 6},
        {"nombre": "Televisor LED 50\"", "cantidad": 1, "horas_uso": 4},
        {"nombre": "Router", "cantidad": 1, "horas_uso": 24},
    ]
    recomendacion = calcular_dimensionamiento(equipos, paneles_cfg, inversor_cfg, bateria_cfg)
    resultado = generar_presupuesto(
        datos_cliente=cliente,
        paneles=paneles_cfg,
        inversor=inversor_cfg,
        bateria=bateria_cfg,
        equipos_uso=equipos,
        costos_adicionales=costos,
        porcentaje_iva=19,
        recomendacion=recomendacion,
    )
    print(f"PDF generado: {resultado['archivo']}")
    print(f"Consumo diario estimado: {resultado['consumo_diario_wh']:.0f} Wh/dia")
    print(f"Total final: {clp(resultado['total'])}")
