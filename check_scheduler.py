#!/usr/bin/env python3
"""
Check Scheduler Status - Verifica status do scheduler automático
"""

import subprocess
import os
from pathlib import Path

def check_scheduler_process():
    """Verifica se o scheduler está rodando"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout
        
        scheduler_processes = []
        for line in processes.split('\n'):
            if 'trending_scheduler.py' in line and 'grep' not in line:
                scheduler_processes.append(line.strip())
        
        return scheduler_processes
    except Exception as e:
        print(f"Erro ao verificar processos: {e}")
        return []

def check_log_file():
    """Verifica o arquivo de log"""
    log_file = Path("logs/scheduler.log")
    
    if not log_file.exists():
        return "Log file não encontrado"
    
    try:
        # Últimas 10 linhas do log
        with open(log_file, 'r') as f:
            lines = f.readlines()
            return lines[-10:] if lines else ["Log vazio"]
    except Exception as e:
        return [f"Erro ao ler log: {e}"]

def main():
    print("🔍 VERIFICANDO STATUS DO SCHEDULER")
    print("="*50)
    
    # Verifica processos
    processes = check_scheduler_process()
    
    if processes:
        print(f"✅ SCHEDULER ATIVO - {len(processes)} processo(s) encontrado(s):")
        for i, process in enumerate(processes, 1):
            print(f"   {i}. {process}")
        print()
    else:
        print("❌ SCHEDULER NÃO ESTÁ RODANDO")
        print()
    
    # Verifica logs
    print("📋 ÚLTIMAS ENTRADAS DO LOG:")
    print("-" * 30)
    log_lines = check_log_file()
    
    if isinstance(log_lines, str):
        print(log_lines)
    else:
        for line in log_lines:
            print(line.rstrip())
    
    print("\n" + "="*50)
    
    if processes:
        print("🎯 STATUS: Scheduler executando normalmente")
        print("📅 Próxima execução: Em até 2 horas")
        print("📊 Logs em tempo real: tail -f logs/scheduler.log")
    else:
        print("⚠️ STATUS: Scheduler parado")
        print("🚀 Para iniciar: python3 trending_scheduler.py --mode start --interval 2")

if __name__ == "__main__":
    main()