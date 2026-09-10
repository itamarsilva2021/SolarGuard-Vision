"""
Parser especializado de metadados XMP para aeronaves DJI Enterprise (Matrice 4T).
Suporta namespaces proprietários 'http://www.dji.com/drone-dji/1.0/' e formatos
flexíveis de atributos XML e nós de elementos.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import re
import xml.etree.ElementTree as ET
from src.core.logger import get_logger

logger = get_logger("DjiXmpParser")


class DjiXmpParser:
    """
    Decodificador robusto de blocos XMP embutidos em arquivos JPEG / R-JPEG da DJI.
    Utiliza uma abordagem híbrida: XML DOM/ElementTree para estrutura formal e
    expressões regulares resilientes para blocos fragmentados ou com formatação mista.
    """

    DJI_NAMESPACE_URI = "http://www.dji.com/drone-dji/1.0/"

    @classmethod
    def extract_raw_xmp_string(cls, file_path: str | Path) -> Optional[str]:
        """
        Localiza e extrai a cadeia de texto XML do bloco XMP do arquivo binário.
        
        :param file_path: Caminho para o arquivo JPEG / R-JPEG.
        :return: String com o bloco XML ou None se não encontrado.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            start_idx = content.find(b"<x:xmpmeta")
            end_idx = content.find(b"</x:xmpmeta>")

            if start_idx != -1 and end_idx != -1:
                end_idx += len(b"</x:xmpmeta>")
                return content[start_idx:end_idx].decode("utf-8", errors="ignore")

            # Fallback para marcadores simplificados
            start_rdf = content.find(b"<rdf:RDF")
            end_rdf = content.find(b"</rdf:RDF>")
            if start_rdf != -1 and end_rdf != -1:
                end_rdf += len(b"</rdf:RDF>")
                return content[start_rdf:end_rdf].decode("utf-8", errors="ignore")

        except Exception as ex:
            logger.warning(f"Erro ao extrair string XMP de {file_path.name}: {ex}")

        return None

    @classmethod
    def parse_xmp(cls, file_path: str | Path) -> Dict[str, Any]:
        """
        Extrai todos os metadados do DJI Matrice 4T a partir do XMP do arquivo.
        
        :param file_path: Caminho do arquivo.
        :return: Dicionário contendo todos os campos decodificados com tipos apropriados.
        """
        xmp_str = cls.extract_raw_xmp_string(file_path)
        if not xmp_str:
            return {}

        return cls.parse_xmp_string(xmp_str)

    @classmethod
    def parse_xmp_string(cls, xmp_str: str) -> Dict[str, Any]:
        """
        Processa o conteúdo textual XMP e extrai os campos DJI Matrice 4T.
        
        :param xmp_str: Conteúdo XML do bloco XMP.
        :return: Dicionário com dados tipados.
        """
        data: Dict[str, Any] = {}

        # 1. Tentativa via XML DOM (ElementTree)
        try:
            # Limpa possíveis prefixos de envelope se necessário
            root = ET.fromstring(xmp_str)
            for elem in root.iter():
                # Elementos com namespace DJI
                tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if elem.text and elem.text.strip():
                    data[tag_name] = elem.text.strip()

                # Atributos no elemento
                for attr_key, attr_val in elem.attrib.items():
                    clean_attr = attr_key.split("}")[-1] if "}" in attr_key else attr_key
                    data[clean_attr] = attr_val.strip()
        except Exception as xml_err:
            logger.debug(f"Parsing XML formal falhou, recorrendo a Regex multiformato: {xml_err}")

        # 2. Complementação e garantia via Regex Multiformato (lê nós e atributos)
        # Campos de interesse do DJI Enterprise Matrice 4T
        fields_to_scan = [
            # Gimbal
            "GimbalPitchDegree", "GimbalRollDegree", "GimbalYawDegree",
            # Drone Flight
            "FlightPitchDegree", "FlightRollDegree", "FlightYawDegree",
            # Altitudes
            "RelativeAltitude", "AbsoluteAltitude", "RtkAltitude",
            # RTK
            "RtkFlag", "RtkStdLat", "RtkStdLon", "RtkStdHgt", "RtkDiffAge",
            # Radiometria / Câmera Térmica
            "ThermalGainMode", "Emissivity", "ReflectedTemperature", "Distance", "RelativeHumidity",
            # Hardware e Identificação
            "Model", "DroneSerialNumber", "CameraSerialNumber", "CameraType",
            # Calibração Óptica
            "CalibratedFocalLength", "CalibratedOpticalCenterX", "CalibratedOpticalCenterY", "DewarpData",
        ]

        for field in fields_to_scan:
            if field not in data or data[field] is None:
                val = cls._regex_extract_field(xmp_str, field)
                if val is not None:
                    data[field] = val

        # 3. Normalização de Tipos de Dados
        converted: Dict[str, Any] = {}
        for k, v in data.items():
            converted[k] = cls._cast_value(k, v)

        return converted

    @staticmethod
    def _regex_extract_field(xml_text: str, field_name: str) -> Optional[str]:
        """
        Busca uma tag tanto como atributo XML quanto como elemento XML aberto,
        suportando prefixos 'drone-dji:', 'dji:' ou sem prefixo.
        """
        # Formato 1: drone-dji:FieldName="valor" ou dji:FieldName="valor"
        attr_pattern = rf'(?:drone-dji|dji):{field_name}=["\']([^"\']+)["\']'
        match = re.search(attr_pattern, xml_text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Formato 2: <drone-dji:FieldName>valor</drone-dji:FieldName>
        elem_pattern = rf'<(?:drone-dji|dji):{field_name}[^>]*>([^<]+)</(?:drone-dji|dji):{field_name}>'
        match = re.search(elem_pattern, xml_text, re.IGNORECASE)
        if match:
            return match.group(1)

        # Formato 3: rdf:Description com atributo simples FieldName="valor"
        generic_attr = rf'\b{field_name}=["\']([^"\']+)["\']'
        match = re.search(generic_attr, xml_text, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def _cast_value(key: str, val: Any) -> Any:
        """Converte strings numéricas em float ou int conforme semântica do campo."""
        if not isinstance(val, str):
            return val

        val = val.strip()

        # Inteiros conhecidos
        if key in ["RtkFlag", "RtkDiffAge"]:
            try:
                return int(float(val))
            except ValueError:
                return val

        # Floats conhecidos (altitudes, ângulos, desvios, radiometria)
        float_fields = {
            "GimbalPitchDegree", "GimbalRollDegree", "GimbalYawDegree",
            "FlightPitchDegree", "FlightRollDegree", "FlightYawDegree",
            "RelativeAltitude", "AbsoluteAltitude", "RtkAltitude",
            "RtkStdLat", "RtkStdLon", "RtkStdHgt",
            "Emissivity", "ReflectedTemperature", "Distance", "RelativeHumidity",
            "CalibratedFocalLength", "CalibratedOpticalCenterX", "CalibratedOpticalCenterY",
        }
        if key in float_fields:
            try:
                return float(val)
            except ValueError:
                return val

        return val
