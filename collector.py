import os
import sys

def collect_code(root_dir, output_filename):
    # 1. Находим директорию, где лежит main.py
    # Если запуск идет из корня проекта, это будет текущая папка
    # Если нет, ищем main.py в дереве проекта
    base_path = os.path.abspath(root_dir)
    target_dir = base_path
    
    for root, dirs, files in os.walk(base_path):
        if 'main.py' in files:
            target_dir = root
            break
    
    output_file = os.path.join(target_dir, output_filename)
    
    print(f"🔍 Поиск файлов в: {base_path}")
    print(f"📝 Целевой файл: {output_file}")
    print("-" * 50)

    files_processed = 0
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for root, dirs, files in os.walk(base_path):
                # Пропускаем лишние папки
                if any(ignored in root for ignored in ['venv', '.git', '__pycache__', '.idea', '.vscode']):
                    continue
                
                for file in files:
                    # Собираем только нужные расширения, исключая сам файл результата и скрипт сборщика
                    if file.endswith(('.py', '.env', '.txt')) and \
                       file != output_filename and \
                       file != os.path.basename(__file__):
                        
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, base_path)
                        
                        print(f"📄 Добавляю: {rel_path}")
                        
                        f.write(f"\n\n{'='*60}\n")
                        f.write(f"ПУТЬ К ФАЙЛУ: {rel_path}\n")
                        f.write(f"{'='*60}\n\n")
                        
                        try:
                            with open(full_path, 'r', encoding='utf-8') as code_file:
                                f.write(code_file.read())
                            files_processed += 1
                        except Exception as e:
                            error_msg = f"Ошибка при чтении файла {file}: {e}"
                            f.write(error_msg)
                            print(f"⚠️ {error_msg}")

        print("-" * 50)
        print(f"✅ Готово! Обработано файлов: {files_processed}")
        print(f"📍 Файл сохранен в: {output_file}")

    except Exception as e:
        print(f"❌ Критическая ошибка при записи: {e}")

if __name__ == "__main__":
    # Собираем всё из текущей папки и сохраняем в project_context.txt
    collect_code('.', 'project_context.txt')