import json
import re
from typing import Optional, Dict, Any
from datetime import datetime

from database import Result

class ResultParser:
    def __init__(self):
        # Маппинг уровней серьезности
        self.severity_mapping = {
            "info": "info",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "critical": "critical",
            "unknown": "info"
        }
    
    def parse_result(self, result_data: Dict[str, Any], task_id: int) -> Optional[Result]:
        """Парсинг результата Nuclei в формате JSON"""
        try:
            # Извлечение основных полей
            template_id = result_data.get("template-id", "")
            template_name = result_data.get("template", template_id)
            
            # Информация о хосте
            host = result_data.get("host", "")
            matched_at = result_data.get("matched-at", host)
            
            # Протокол
            if matched_at.startswith("https://"):
                protocol = "https"
            elif matched_at.startswith("http://"):
                protocol = "http"
            else:
                protocol = result_data.get("type", "unknown")
            
            # Уровень серьезности
            info = result_data.get("info", {})
            severity = info.get("severity", "info").lower()
            severity = self.severity_mapping.get(severity, "info")
            
            # Название matcher'а
            matcher_name = result_data.get("matcher-name", "")
            
            # Извлеченные результаты
            extracted_results = result_data.get("extracted-results", [])
            if extracted_results:
                extracted_results = json.dumps(extracted_results)
            else:
                extracted_results = None
            
            # Curl команда
            curl_command = result_data.get("curl-command", "")
            
            # Создание результата
            result = Result(
                task_id=task_id,
                template_name=template_name,
                protocol=protocol,
                severity=severity,
                target=host,
                matched_at=matched_at,
                matcher_name=matcher_name,
                extracted_results=extracted_results,
                curl_command=curl_command,
                raw_output=json.dumps(result_data)
            )
            
            return result
            
        except Exception as e:
            print(f"Error parsing result: {str(e)}")
            return None
    
    def parse_text_result(self, line: str, task_id: int) -> Optional[Result]:
        """Парсинг результата Nuclei в текстовом формате"""
        # Формат: [template-id] [protocol] [severity] target
        pattern = r"\[([^\]]+)\]\s+\[([^\]]+)\]\s+\[([^\]]+)\]\s+(.+)"
        match = re.match(pattern, line.strip())
        
        if match:
            template_name = match.group(1)
            protocol = match.group(2)
            severity = match.group(3).lower()
            target = match.group(4)
            
            result = Result(
                task_id=task_id,
                template_name=template_name,
                protocol=protocol,
                severity=self.severity_mapping.get(severity, "info"),
                target=target,
                matched_at=target,
                raw_output=line
            )
            
            return result
        
        return None
    
    def parse_nuclei_stats(self, stats_line: str) -> Dict[str, Any]:
        """Парсинг статистики Nuclei"""
        # Пример: [INF] Templates: 150 | Hosts: 100 | RPS: 145 | Matched: 25
        stats = {}
        
        # Извлечение количества шаблонов
        templates_match = re.search(r"Templates:\s*(\d+)", stats_line)
        if templates_match:
            stats["templates"] = int(templates_match.group(1))
        
        # Извлечение количества хостов
        hosts_match = re.search(r"Hosts:\s*(\d+)", stats_line)
        if hosts_match:
            stats["hosts"] = int(hosts_match.group(1))
        
        # Извлечение RPS
        rps_match = re.search(r"RPS:\s*(\d+)", stats_line)
        if rps_match:
            stats["rps"] = int(rps_match.group(1))
        
        # Извлечение количества совпадений
        matched_match = re.search(r"Matched:\s*(\d+)", stats_line)
        if matched_match:
            stats["matched"] = int(matched_match.group(1))
        
        return stats
    
    def calculate_progress(self, stats: Dict[str, Any], total_targets: int) -> float:
        """Расчет прогресса сканирования"""
        if not stats or total_targets == 0:
            return 0.0
        
        processed_hosts = stats.get("hosts", 0)
        progress = (processed_hosts / total_targets) * 100
        
        return min(progress, 100.0)
    
    def group_results_by_severity(self, results: list) -> Dict[str, list]:
        """Группировка результатов по уровню серьезности"""
        grouped = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": []
        }
        
        for result in results:
            severity = result.severity or "info"
            if severity in grouped:
                grouped[severity].append(result)
        
        return grouped
    
    def group_results_by_template(self, results: list) -> Dict[str, list]:
        """Группировка результатов по шаблону"""
        grouped = {}
        
        for result in results:
            template = result.template_name or "unknown"
            if template not in grouped:
                grouped[template] = []
            grouped[template].append(result)
        
        return grouped
    
    def filter_results(
        self,
        results: list,
        severity: Optional[str] = None,
        protocol: Optional[str] = None,
        template_name: Optional[str] = None,
        target_contains: Optional[str] = None
    ) -> list:
        """Фильтрация результатов по различным критериям"""
        filtered = results
        
        if severity:
            filtered = [r for r in filtered if r.severity == severity]
        
        if protocol:
            filtered = [r for r in filtered if r.protocol == protocol]
        
        if template_name:
            filtered = [r for r in filtered if template_name in r.template_name]
        
        if target_contains:
            filtered = [r for r in filtered if target_contains in r.target]
        
        return filtered