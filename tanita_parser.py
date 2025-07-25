#!/usr/bin/env python3
"""
Tanita BC-601/BC-603 FS Data Parser
Lee archivos CSV de la báscula Tanita y genera un reporte PDF con todas las mediciones.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import argparse
import matplotlib.pyplot as plt
import numpy as np
import tempfile

# Mapeo de códigos de Tanita a nombres legibles
TANITA_MAPPINGS = {
    "0": "Desconocido: 16",
    "~0": "Unidad de longitud",
    "~1": "Unidad de masa",
    "~2": "Desconocido: 4",
    "~3": "Desconocido: 3",
    "Bt": "Modo atleta (0=Normal, 2=Atleta)",
    "Wk": "Masa corporal (kg)",
    "MI": "Índice de masa corporal (IMC)",
    "MO": "Modelo",
    "DT": "Fecha de medición",
    "Ti": "Hora de medición",
    "GE": "Género",
    "AG": "Edad",
    "Hm": "Altura (cm)",
    "AL": "Nivel de actividad",
    "FW": "Grasa corporal total %",
    "Fr": "Grasa del brazo (derecho) %",
    "Fl": "Grasa del brazo (izquierdo) %",
    "FR": "Grasa de la pierna (derecha) %",
    "FL": "Grasa de la pierna (izquierda) %",
    "FT": "Grasa del torso %",
    "mW": "Músculo corporal total %",
    "mr": "Músculo del brazo (derecho) %",
    "ml": "Músculo del brazo (izquierdo) %",
    "mR": "Músculo de la pierna (derecha) %",
    "mL": "Músculo de la pierna (izquierda) %",
    "mT": "Músculo del torso %",
    "bw": "Masa ósea estimada (kg)",
    "IF": "Índice de grasa visceral",
    "rA": "Edad metabólica estimada",
    "rD": "Ingesta calórica diaria (ICD)",
    "ww": "Agua corporal total %",
    "CS": "Desconocido: BC",
}


class TanitaParser:
    def __init__(self):
        self.measurements = []
        self.profiles = {}

    def parse_csv_file(self, file_path, file_type="measurement"):
        """Parsea un archivo CSV de Tanita"""
        if not os.path.exists(file_path):
            print(f"Error: El archivo {file_path} no existe")
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                reader = csv.reader(file)

                for row_num, row in enumerate(reader):
                    if not row or len(row) < 2:
                        continue

                    if file_type == "measurement":
                        self._parse_measurement_row(row, file_path, row_num)
                    elif file_type == "profile":
                        self._parse_profile_row(row, file_path, row_num)

        except Exception as e:
            print(f"Error leyendo {file_path}: {e}")

    def _parse_measurement_row(self, row, file_path, row_num):
        """Parsea una fila de medición"""
        measurement = {
            "file": os.path.basename(file_path),
            "row": row_num + 1,
            "raw_data": row,
        }

        # Procesar columnas alternadas (header, valor)
        for i in range(0, len(row) - 1, 2):
            header = row[i].strip()
            value = row[i + 1].strip() if i + 1 < len(row) else ""

            if header in TANITA_MAPPINGS:
                measurement[TANITA_MAPPINGS[header]] = value
            else:
                measurement[f"Unknown_{header}"] = value

        self.measurements.append(measurement)

    def _parse_profile_row(self, row, file_path, row_num):
        """Parsea una fila de perfil (si es necesario)"""
        # Por ahora solo guardamos los datos crudos del perfil
        profile_key = f"{os.path.basename(file_path)}_row_{row_num}"
        self.profiles[profile_key] = {
            "file": os.path.basename(file_path),
            "row": row_num + 1,
            "data": row,
        }

    def _get_sorted_measurements(self):
        """Devuelve las mediciones ordenadas por fecha y hora (de más antigua a más reciente)"""

        def parse_datetime(measurement):
            fecha = measurement.get("Fecha de medición")
            hora = measurement.get("Hora de medición")
            if fecha and hora:
                try:
                    # Formato esperado: dd/mm/yyyy y HH:MM:SS
                    return datetime.strptime(f"{fecha} {hora}", "%d/%m/%Y %H:%M:%S")
                except Exception:
                    pass
            return datetime.min

        return sorted(self.measurements, key=parse_datetime)

    def _plot_radar(self, values, labels, title, color="#1f77b4"):
        """Genera una gráfica radar y devuelve la ruta de la imagen temporal"""
        N = len(labels)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        values += values[:1]  # cerrar el pentágono
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(3, 3), subplot_kw=dict(polar=True))
        ax.plot(angles, values, color=color, linewidth=2)
        ax.fill(angles, values, color=color, alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels)
        ax.set_yticklabels([])
        ax.set_title(title, size=10, y=1.1)
        plt.tight_layout()
        tmpfile = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmpfile.name, bbox_inches="tight")
        plt.close(fig)
        return tmpfile.name

    def _plot_colored_bar(
        self, value, ranges, bar_colors, labels, title, units="", width=5, height=0.9
    ):
        """Genera una barra de colores con el valor marcado y devuelve la ruta de la imagen temporal"""
        fig, ax = plt.subplots(figsize=(width, height + 0.7))
        # Dibujar los rangos de color (barra más gruesa)
        for i, (r, c) in enumerate(zip(ranges, bar_colors)):
            ax.barh(0, r[1] - r[0], left=r[0], color=c, edgecolor="black", height=0.7)
            # Etiquetas de rango (arriba de la barra)
            ax.text(
                (r[0] + r[1]) / 2, 0.5, labels[i], ha="center", va="bottom", fontsize=10
            )
        # Línea del valor
        ax.axvline(value, color="black", linewidth=2)
        # Valor numérico debajo de la barra, bien separado
        ax.text(value, -0.5, f"{value:.1f}{units}", ha="center", va="top", fontsize=12)
        # Título
        ax.set_title(title, fontsize=13, pad=20)
        ax.set_yticks([])
        ax.set_ylim(-0.7, 1.1)
        ax.set_xlim(ranges[0][0], ranges[-1][1])
        ax.set_xticks([])
        plt.tight_layout()
        tmpfile = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        plt.savefig(tmpfile.name, bbox_inches="tight")
        plt.close(fig)
        return tmpfile.name

    def _plot_comparison_chart(
        self,
        measurement1,
        measurement2,
        field_name,
        title,
        units="",
        color1="#3498db",
        color2="#e74c3c",
    ):
        """Genera una gráfica comparativa entre dos mediciones, usando fechas reales en el eje X y ajustando la altura de las barras"""
        try:
            # Obtener valores de ambas mediciones
            value1 = measurement1.get(field_name)
            value2 = measurement2.get(field_name)

            if value1 is None or value2 is None:
                return None

            # Convertir a números
            try:
                val1 = float(str(value1).replace("%", "").replace(",", "."))
                val2 = float(str(value2).replace("%", "").replace(",", "."))
            except:
                return None

            # Obtener fechas para etiquetas
            def get_fecha_hora(m):
                f = m.get("Fecha de medición", "?")
                h = m.get("Hora de medición", "?")
                return f"{f}\n{h}" if f != "?" and h != "?" else f

            label1 = get_fecha_hora(measurement1)
            label2 = get_fecha_hora(measurement2)

            # Crear gráfica de barras comparativa
            fig, ax = plt.subplots(figsize=(7, 5))

            # Datos para la gráfica
            measurements = [label1, label2]
            values = [val1, val2]
            colors = [color1, color2]

            # Crear barras
            bars = ax.bar(
                measurements,
                values,
                color=colors,
                alpha=0.7,
                edgecolor="black",
                linewidth=1,
            )

            # Añadir valores en las barras
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height + (max(values) - min(values)) * 0.05 + 0.5,
                    f"{value:.1f}{units}",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=13,
                )

            # Calcular diferencia
            diff = val2 - val1
            diff_text = f"Diferencia: {diff:+.1f}{units}"

            # Añadir línea de diferencia
            if abs(diff) > 0.1:  # Solo mostrar si hay diferencia significativa
                ax.axhline(y=val1, color="gray", linestyle="--", alpha=0.5)
                ax.text(
                    0.5,
                    val1 + (max(values) - min(values)) * 0.15 + 1,
                    diff_text,
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    fontsize=13,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.7),
                )

            # Configurar gráfica
            ax.set_title(title, fontsize=15, fontweight="bold", pad=20)
            ax.set_ylabel(f"Valor {units}", fontsize=13)
            ax.grid(True, alpha=0.3)

            # Ajustar límites del eje Y para que las barras sean más altas y los valores se vean bien
            min_val = min(values)
            max_val = max(values)
            if max_val == min_val:
                margin = max_val * 0.2 if max_val != 0 else 1
            else:
                margin = (max_val - min_val) * 0.5 + 1
            ax.set_ylim(max(0, min_val - margin), max_val + margin)

            plt.tight_layout()

            # Guardar imagen temporal
            tmpfile = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            plt.savefig(tmpfile.name, bbox_inches="tight", dpi=150)
            plt.close(fig)
            return tmpfile.name

        except Exception as e:
            print(f"Error creando gráfica comparativa para {field_name}: {e}")
            return None

    def _plot_radar_comparison(
        self,
        measurement1,
        measurement2,
        labels,
        keys,
        title,
        color1="#3498db",
        color2="#e74c3c",
    ):
        """Genera una gráfica radar comparativa entre dos mediciones"""
        try:
            # Obtener valores de ambas mediciones
            values1 = []
            values2 = []

            for k in keys:
                v1 = measurement1.get(k)
                v2 = measurement2.get(k)

                try:
                    val1 = (
                        float(str(v1).replace("%", "").replace(",", "."))
                        if v1 is not None
                        else 0
                    )
                    val2 = (
                        float(str(v2).replace("%", "").replace(",", "."))
                        if v2 is not None
                        else 0
                    )
                except:
                    val1 = val2 = 0

                values1.append(val1)
                values2.append(val2)

            if not any(values1) and not any(values2):
                return None

            # Crear gráfica radar
            N = len(labels)
            angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()

            # Cerrar los polígonos
            values1 += values1[:1]
            values2 += values2[:1]
            angles += angles[:1]

            fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

            # Dibujar ambas mediciones
            ax.plot(
                angles,
                values1,
                color=color1,
                linewidth=3,
                label="Medición 1",
                marker="o",
            )
            ax.fill(angles, values1, color=color1, alpha=0.25)

            ax.plot(
                angles,
                values2,
                color=color2,
                linewidth=3,
                label="Medición 2",
                marker="s",
            )
            ax.fill(angles, values2, color=color2, alpha=0.25)

            # Configurar gráfica
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, fontsize=10)
            ax.set_yticklabels([])
            ax.set_title(title, size=14, y=1.1, fontweight="bold")
            ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))

            plt.tight_layout()

            # Guardar imagen temporal
            tmpfile = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            plt.savefig(tmpfile.name, bbox_inches="tight", dpi=150)
            plt.close(fig)
            return tmpfile.name

        except Exception as e:
            print(f"Error creando gráfica radar comparativa: {e}")
            return None

    def generate_pdf_report(self, output_path="tanita_report.pdf"):
        """Genera un reporte PDF con todas las mediciones"""
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        story = []

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Centrado
        )

        # Título
        title = Paragraph("Reporte de Mediciones Tanita BC-601/BC-603 FS", title_style)
        story.append(title)
        story.append(Spacer(1, 20))

        # Información del reporte
        report_info = f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        story.append(Paragraph(report_info, styles["Normal"]))
        story.append(Spacer(1, 20))

        # Resumen
        summary = f"Total de mediciones encontradas: {len(self.measurements)}"
        story.append(Paragraph(summary, styles["Heading2"]))
        story.append(Spacer(1, 20))

        if not self.measurements:
            story.append(
                Paragraph(
                    "No se encontraron mediciones para procesar.", styles["Normal"]
                )
            )
        else:
            # Generar tabla para cada medición
            for i, measurement in enumerate(self.measurements):
                story.append(
                    Paragraph(
                        f"Medición {i+1} - {measurement.get('file', 'Archivo desconocido')}",
                        styles["Heading3"],
                    )
                )
                story.append(Spacer(1, 10))

                # Crear tabla de datos
                table_data = []
                table_data.append(["Campo", "Valor"])

                # Ordenar campos importantes primero
                important_fields = [
                    "Fecha de Medición",
                    "Hora de Medición",
                    "Género",
                    "Edad",
                    "Altura (cm)",
                    "Peso (kg)",
                    "Índice de Masa Corporal (IMC)",
                    "Grasa Corporal Total (%)",
                    "Masa Muscular Total (%)",
                    "Agua Corporal Total (%)",
                    "Masa Ósea Estimada (kg)",
                    "Nivel de Grasa Visceral",
                    "Edad Metabólica Estimada",
                    "Ingesta Calórica Diaria (ICD)",
                ]

                # Agregar campos importantes
                for field in important_fields:
                    if field in measurement:
                        value = str(measurement[field])
                        # Traducción especial para Género
                        if field == "Género":
                            if value == "1":
                                value = "Hombre"
                            elif value == "2":
                                value = "Mujer"
                        table_data.append([field, value])

                # Agregar campos de grasa por región
                fat_fields = [
                    "Grasa del brazo (derecho) %",
                    "Grasa del brazo (izquierdo) %",
                    "Grasa de la pierna (derecha) %",
                    "Grasa de la pierna (izquierda) %",
                    "Grasa del torso %",
                ]
                for field in fat_fields:
                    if field in measurement:
                        table_data.append([field, str(measurement[field])])

                # Agregar campos de músculo por región
                muscle_fields = [
                    "Músculo del brazo (derecho) %",
                    "Músculo del brazo (izquierdo) %",
                    "Músculo de la pierna (derecha) %",
                    "Músculo de la pierna (izquierda) %",
                    "Músculo del torso %",
                ]
                for field in muscle_fields:
                    if field in measurement:
                        table_data.append([field, str(measurement[field])])

                # Agregar otros campos
                for key, value in measurement.items():
                    # Mostrar solo campos conocidos y relevantes
                    if (
                        key not in important_fields
                        and key not in fat_fields
                        and key not in muscle_fields
                        and not key.startswith("file")
                        and not key.startswith("row")
                        and not key.startswith("raw_data")
                        and not key.startswith("Unknown_")
                        and not key.startswith("Desconocido:")
                        and key in TANITA_MAPPINGS.values()
                    ):
                        table_data.append([key, str(value)])

                # Crear tabla
                table = Table(table_data, colWidths=[2.5 * inch, 2 * inch])
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                            ("GRID", (0, 0), (-1, -1), 1, colors.black),
                            ("FONTSIZE", (0, 1), (-1, -1), 9),
                        ]
                    )
                )

                story.append(table)
                story.append(Spacer(1, 20))

                # Obtener sexo para rangos
                genero = measurement.get("Género", "").lower()
                if genero in ["1", "hombre", "m", "male"]:
                    sexo = "hombre"
                elif genero in ["2", "mujer", "f", "female"]:
                    sexo = "mujer"
                else:
                    sexo = "otro"
                # --- Grasa corporal % ---
                grasa = measurement.get("Grasa corporal total %")
                try:
                    grasa = float(str(grasa).replace("%", "").replace(",", "."))
                except:
                    grasa = None
                if grasa is not None:
                    if sexo == "hombre":
                        ranges = [(0, 8), (8, 20), (20, 25), (25, 45)]
                        bar_colors = ["#b3c6ff", "#b6fcb6", "#ffe066", "#ff9999"]
                        labels = ["Bajo", "Óptimo", "Alto", "Muy alto"]
                    elif sexo == "mujer":
                        ranges = [(0, 21), (21, 33), (33, 39), (39, 55)]
                        bar_colors = ["#b3c6ff", "#b6fcb6", "#ffe066", "#ff9999"]
                        labels = ["Bajo", "Óptimo", "Alto", "Muy alto"]
                    else:
                        ranges = [(0, 10), (10, 20), (20, 30), (30, 50)]
                        bar_colors = ["#b3c6ff", "#b6fcb6", "#ffe066", "#ff9999"]
                        labels = ["Bajo", "Óptimo", "Alto", "Muy alto"]
                    img = self._plot_colored_bar(
                        grasa,
                        ranges,
                        bar_colors,
                        labels,
                        "Análisis de grasa corporal [%]",
                        units="%",
                    )
                    story.append(Image(img, width=300, height=60))
                    story.append(Spacer(1, 10))
                # --- IMC ---
                imc = measurement.get("Índice de masa corporal (IMC)")
                try:
                    imc = float(str(imc).replace(",", "."))
                except:
                    imc = None
                if imc is not None:
                    ranges = [(0, 18.5), (18.5, 25), (25, 30), (30, 40)]
                    bar_colors = ["#b3c6ff", "#b6fcb6", "#ffe066", "#ff9999"]
                    labels = ["Bajo peso", "Normal", "Sobrepeso", "Obesidad"]
                    img = self._plot_colored_bar(
                        imc, ranges, bar_colors, labels, "Análisis de IMC [kg/m²]"
                    )
                    story.append(Image(img, width=300, height=60))
                    story.append(Spacer(1, 10))
                # --- Masa muscular % ---
                musc = measurement.get("Músculo corporal total %")
                try:
                    musc = float(str(musc).replace("%", "").replace(",", "."))
                except:
                    musc = None
                if musc is not None:
                    if sexo == "hombre":
                        ranges = [(0, 42), (42, 49), (49, 56), (56, 70)]
                        bar_colors = ["#ff9999", "#ffe066", "#b6fcb6", "#b3c6ff"]
                        labels = ["Muy baja", "Baja", "Óptima", "Alta"]
                    elif sexo == "mujer":
                        ranges = [(0, 30), (30, 36), (36, 42), (42, 60)]
                        bar_colors = ["#ff9999", "#ffe066", "#b6fcb6", "#b3c6ff"]
                        labels = ["Muy baja", "Baja", "Óptima", "Alta"]
                    else:
                        ranges = [(0, 30), (30, 40), (40, 50), (50, 70)]
                        bar_colors = ["#ff9999", "#ffe066", "#b6fcb6", "#b3c6ff"]
                        labels = ["Muy baja", "Baja", "Óptima", "Alta"]
                    img = self._plot_colored_bar(
                        musc,
                        ranges,
                        bar_colors,
                        labels,
                        "Análisis de masa muscular [%]",
                        units="%",
                    )
                    story.append(Image(img, width=300, height=60))
                    story.append(Spacer(1, 10))
                # --- Agua corporal % ---
                agua = measurement.get("Agua corporal total %")
                try:
                    agua = float(str(agua).replace("%", "").replace(",", "."))
                except:
                    agua = None
                if agua is not None:
                    if sexo == "hombre":
                        ranges = [(0, 50), (50, 65), (65, 80)]
                        bar_colors = ["#ffe066", "#b6fcb6", "#b3c6ff"]
                        labels = ["Bajo", "Normal", "Alto"]
                    elif sexo == "mujer":
                        ranges = [(0, 45), (45, 60), (60, 80)]
                        bar_colors = ["#ffe066", "#b6fcb6", "#b3c6ff"]
                        labels = ["Bajo", "Normal", "Alto"]
                    else:
                        ranges = [(0, 45), (45, 60), (60, 80)]
                        bar_colors = ["#ffe066", "#b6fcb6", "#b3c6ff"]
                        labels = ["Bajo", "Normal", "Alto"]
                    img = self._plot_colored_bar(
                        agua,
                        ranges,
                        bar_colors,
                        labels,
                        "Análisis de agua corporal [%]",
                        units="%",
                    )
                    story.append(Image(img, width=300, height=60))
                    story.append(Spacer(1, 10))
                # --- Grasa visceral ---
                visceral = measurement.get("Índice de grasa visceral")
                try:
                    visceral = float(str(visceral).replace(",", "."))
                except:
                    visceral = None
                if visceral is not None:
                    ranges = [(1, 10), (10, 15), (15, 30)]
                    bar_colors = ["#b6fcb6", "#ffe066", "#ff9999"]
                    labels = ["Óptima", "Alta", "Muy alta"]
                    img = self._plot_colored_bar(
                        visceral, ranges, bar_colors, labels, "Grasa visceral [nivel]"
                    )
                    story.append(Image(img, width=300, height=60))
                    story.append(Spacer(1, 10))

                # --- Gráficas pentagonales (radar) ---
                # Gráfica radar de grasa segmentada
                fat_labels = [
                    "Tronco",
                    "Brazo derecho",
                    "Brazo izquierdo",
                    "Pierna derecha",
                    "Pierna izquierda",
                ]
                fat_keys = [
                    "Grasa del torso %",
                    "Grasa del brazo (derecho) %",
                    "Grasa del brazo (izquierdo) %",
                    "Grasa de la pierna (derecha) %",
                    "Grasa de la pierna (izquierda) %",
                ]
                fat_values = []
                for k in fat_keys:
                    v = measurement.get(k)
                    try:
                        fat_values.append(
                            float(str(v).replace("%", "").replace(",", "."))
                            if v is not None
                            else 0
                        )
                    except:
                        fat_values.append(0)
                if any(fat_values):
                    fat_img = self._plot_radar(
                        fat_values,
                        fat_labels,
                        "Distribución del segmento - Nivel de grasa",
                        color="#e67e22",
                    )
                    story.append(Spacer(1, 10))
                    story.append(
                        Paragraph(
                            "Distribución del segmento - Nivel de grasa",
                            styles["Normal"],
                        )
                    )
                    story.append(Spacer(1, 5))
                    story.append(Image(fat_img, width=200, height=200))
                # Gráfica radar de músculo segmentado
                muscle_labels = [
                    "Tronco",
                    "Brazo derecho",
                    "Brazo izquierdo",
                    "Pierna derecha",
                    "Pierna izquierda",
                ]
                muscle_keys = [
                    "Músculo del torso %",
                    "Músculo del brazo (derecho) %",
                    "Músculo del brazo (izquierdo) %",
                    "Músculo de la pierna (derecha) %",
                    "Músculo de la pierna (izquierda) %",
                ]
                muscle_values = []
                for k in muscle_keys:
                    v = measurement.get(k)
                    try:
                        muscle_values.append(
                            float(str(v).replace("%", "").replace(",", "."))
                            if v is not None
                            else 0
                        )
                    except:
                        muscle_values.append(0)
                if any(muscle_values):
                    muscle_img = self._plot_radar(
                        muscle_values,
                        muscle_labels,
                        "Distribución del segmento - Masa muscular",
                        color="#3498db",
                    )
                    story.append(Spacer(1, 10))
                    story.append(
                        Paragraph(
                            "Distribución del segmento - Masa muscular",
                            styles["Normal"],
                        )
                    )
                    story.append(Spacer(1, 5))
                    story.append(Image(muscle_img, width=200, height=200))

                # Agregar salto de página si no es la última medición
                if i < len(self.measurements) - 1:
                    story.append(PageBreak())

        # Sección de comparación entre las dos últimas mediciones
        sorted_measurements = self._get_sorted_measurements()
        if len(sorted_measurements) >= 2:
            story.append(PageBreak())
            story.append(
                Paragraph(
                    "COMPARACIÓN ENTRE LAS DOS ÚLTIMAS MEDICIONES",
                    title_style,
                )
            )
            story.append(Spacer(1, 20))

            # Información de las mediciones comparadas
            last_measurement = sorted_measurements[-1]
            prev_measurement = sorted_measurements[-2]

            comparison_info = f"""
            <b>Medición más reciente:</b> {last_measurement.get('file', 'Archivo desconocido')} - 
            Fecha: {last_measurement.get('Fecha de medición', 'N/A')} {last_measurement.get('Hora de medición', '')}<br/>
            <b>Medición anterior:</b> {prev_measurement.get('file', 'Archivo desconocido')} - 
            Fecha: {prev_measurement.get('Fecha de medición', 'N/A')} {prev_measurement.get('Hora de medición', '')}
            """
            story.append(Paragraph(comparison_info, styles["Normal"]))
            story.append(Spacer(1, 20))

            # Tabla comparativa de valores principales
            comparison_table_data = []
            comparison_table_data.append(
                ["Parámetro", "Medición Anterior", "Medición Actual", "Diferencia"]
            )

            # Campos a comparar
            comparison_fields = [
                ("Masa corporal (kg)", "kg"),
                ("Índice de masa corporal (IMC)", ""),
                ("Grasa corporal total %", "%"),
                ("Músculo corporal total %", "%"),
                ("Agua corporal total %", "%"),
                ("Índice de grasa visceral", ""),
                ("Edad metabólica estimada", "años"),
                ("Ingesta calórica diaria (ICD)", "kcal"),
            ]

            for field, unit in comparison_fields:
                val1 = prev_measurement.get(field)
                val2 = last_measurement.get(field)

                if val1 is not None and val2 is not None:
                    try:
                        num1 = float(str(val1).replace("%", "").replace(",", "."))
                        num2 = float(str(val2).replace("%", "").replace(",", "."))
                        diff = num2 - num1
                        diff_str = f"{diff:+.1f}{unit}"
                        # Color de la diferencia
                        if abs(diff) < 0.1:
                            diff_color = "gray"
                        elif diff > 0:
                            diff_color = "red"
                        else:
                            diff_color = "green"
                        diff_paragraph = Paragraph(
                            f'<font color="{diff_color}">{diff_str}</font>',
                            styles["Normal"],
                        )
                    except:
                        diff_paragraph = Paragraph("N/A", styles["Normal"])
                else:
                    diff_paragraph = Paragraph("N/A", styles["Normal"])

                comparison_table_data.append(
                    [
                        field,
                        str(val1) if val1 is not None else "N/A",
                        str(val2) if val2 is not None else "N/A",
                        diff_paragraph,
                    ]
                )

            # Crear tabla comparativa
            comparison_table = Table(
                comparison_table_data,
                colWidths=[2 * inch, 1.5 * inch, 1.5 * inch, 1 * inch],
            )
            comparison_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 1), (-1, -1), 9),
                        (
                            "ALIGN",
                            (0, 0),
                            (0, -1),
                            "LEFT",
                        ),  # Primera columna alineada a la izquierda
                    ]
                )
            )

            story.append(comparison_table)
            story.append(Spacer(1, 20))

            # Gráficas comparativas principales
            story.append(
                Paragraph(
                    "Evolución de Parámetros Principales",
                    styles["Heading2"],
                )
            )
            story.append(Spacer(1, 15))

            # Gráfica comparativa de peso
            weight_comparison = self._plot_comparison_chart(
                prev_measurement,
                last_measurement,
                "Masa corporal (kg)",
                "Evolución del Peso Corporal",
                units=" kg",
            )
            if weight_comparison:
                story.append(Image(weight_comparison, width=400, height=250))
                story.append(Spacer(1, 10))

            # Gráfica comparativa de IMC
            imc_comparison = self._plot_comparison_chart(
                prev_measurement,
                last_measurement,
                "Índice de masa corporal (IMC)",
                "Evolución del Índice de Masa Corporal",
                units=" kg/m²",
            )
            if imc_comparison:
                story.append(Image(imc_comparison, width=400, height=250))
                story.append(Spacer(1, 10))

            # Gráfica comparativa de composición corporal
            story.append(
                Paragraph(
                    "Evolución de la Composición Corporal",
                    styles["Heading2"],
                )
            )
            story.append(Spacer(1, 15))

            # Crear gráfica de barras apiladas para composición corporal
            try:
                fat1 = float(
                    str(prev_measurement.get("Grasa corporal total %", "0"))
                    .replace("%", "")
                    .replace(",", ".")
                )
                muscle1 = float(
                    str(prev_measurement.get("Músculo corporal total %", "0"))
                    .replace("%", "")
                    .replace(",", ".")
                )
                water1 = float(
                    str(prev_measurement.get("Agua corporal total %", "0"))
                    .replace("%", "")
                    .replace(",", ".")
                )

                fat2 = float(
                    str(last_measurement.get("Grasa corporal total %", "0"))
                    .replace("%", "")
                    .replace(",", ".")
                )
                muscle2 = float(
                    str(last_measurement.get("Músculo corporal total %", "0"))
                    .replace("%", "")
                    .replace(",", ".")
                )
                water2 = float(
                    str(last_measurement.get("Agua corporal total %", "0"))
                    .replace("%", "")
                    .replace(",", ".")
                )

                fig, ax = plt.subplots(figsize=(8, 5))

                # Datos para la gráfica
                measurements = ["Medición Anterior", "Medición Actual"]
                fat_values = [fat1, fat2]
                muscle_values = [muscle1, muscle2]
                water_values = [water1, water2]

                # Crear barras apiladas
                ax.bar(
                    measurements,
                    fat_values,
                    label="Grasa %",
                    color="#ff6b6b",
                    alpha=0.8,
                )
                ax.bar(
                    measurements,
                    muscle_values,
                    bottom=fat_values,
                    label="Músculo %",
                    color="#4ecdc4",
                    alpha=0.8,
                )
                ax.bar(
                    measurements,
                    water_values,
                    bottom=[f + m for f, m in zip(fat_values, muscle_values)],
                    label="Agua %",
                    color="#45b7d1",
                    alpha=0.8,
                )

                # Añadir valores en las barras
                for i, (f, m, w) in enumerate(
                    zip(fat_values, muscle_values, water_values)
                ):
                    total = f + m + w
                    ax.text(
                        i,
                        f / 2,
                        f"{f:.1f}%",
                        ha="center",
                        va="center",
                        fontweight="bold",
                    )
                    ax.text(
                        i,
                        f + m / 2,
                        f"{m:.1f}%",
                        ha="center",
                        va="center",
                        fontweight="bold",
                    )
                    ax.text(
                        i,
                        f + m + w / 2,
                        f"{w:.1f}%",
                        ha="center",
                        va="center",
                        fontweight="bold",
                    )
                    ax.text(
                        i,
                        total + 2,
                        f"Total: {total:.1f}%",
                        ha="center",
                        va="bottom",
                        fontweight="bold",
                    )

                ax.set_title(
                    "Composición Corporal Comparativa",
                    fontsize=14,
                    fontweight="bold",
                    pad=20,
                )
                ax.set_ylabel("Porcentaje (%)", fontsize=12)
                ax.legend()
                ax.grid(True, alpha=0.3)

                plt.tight_layout()

                # Guardar imagen temporal
                tmpfile = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                plt.savefig(tmpfile.name, bbox_inches="tight", dpi=150)
                plt.close(fig)

                story.append(Image(tmpfile.name, width=400, height=250))
                story.append(Spacer(1, 10))

            except Exception as e:
                print(f"Error creando gráfica de composición corporal: {e}")

        # Generar PDF
        doc.build(story)
        print(f"Reporte generado exitosamente: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Parser de archivos CSV de Tanita BC-601/BC-603 FS"
    )
    parser.add_argument(
        "--data-dir", type=str, help="/home/iganan/Escritorio/tanita/DATOS"
    )
    parser.add_argument(
        "--system-dir", type=str, help="Directorio con archivos PROF*.CSV"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tanita_report.pdf",
        help="/home/iganan/Escritorio/tanita/PDFS",
    )
    parser.add_argument(
        "--files", nargs="+", help="Archivos CSV específicos a procesar"
    )

    args = parser.parse_args()

    tanita_parser = TanitaParser()

    # Procesar archivos específicos si se proporcionan
    if args.files:
        for file_path in args.files:
            if "DATA" in file_path.upper():
                tanita_parser.parse_csv_file(file_path, "measurement")
            elif "PROF" in file_path.upper():
                tanita_parser.parse_csv_file(file_path, "profile")
            else:
                print(f"Archivo no reconocido: {file_path}")

    # Procesar directorios si se proporcionan
    if args.data_dir:
        data_dir = Path(args.data_dir)
        if data_dir.exists():
            for csv_file in data_dir.glob("DATA*.CSV"):
                print(f"Procesando archivo de mediciones: {csv_file}")
                tanita_parser.parse_csv_file(str(csv_file), "measurement")
        else:
            print(f"El directorio de datos no existe: {args.data_dir}")

    if args.system_dir:
        system_dir = Path(args.system_dir)
        if system_dir.exists():
            for csv_file in system_dir.glob("PROF*.CSV"):
                print(f"Procesando archivo de perfiles: {csv_file}")
                tanita_parser.parse_csv_file(str(csv_file), "profile")
        else:
            print(f"El directorio del sistema no existe: {args.system_dir}")

    # Si no se proporcionaron argumentos, buscar archivos en el directorio actual
    if not args.files and not args.data_dir and not args.system_dir:
        current_dir = Path(".")
        print("Buscando archivos CSV de Tanita en el directorio actual...")

        for csv_file in current_dir.glob("*.CSV"):
            if "DATA" in csv_file.name.upper():
                print(f"Procesando archivo de mediciones: {csv_file}")
                tanita_parser.parse_csv_file(str(csv_file), "measurement")
            elif "PROF" in csv_file.name.upper():
                print(f"Procesando archivo de perfiles: {csv_file}")
                tanita_parser.parse_csv_file(str(csv_file), "profile")

    # Generar reporte PDF
    if tanita_parser.measurements:
        tanita_parser.generate_pdf_report(args.output)
    else:
        print("No se encontraron mediciones para procesar.")


if __name__ == "__main__":
    main()
