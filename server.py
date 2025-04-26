import os
import hashlib
from flask import Flask, request, jsonify, send_from_directory, make_response
from werkzeug.utils import secure_filename
from typing import Dict, Optional, Tuple

class FileStorageServer:
    def __init__(self, storage_path: str = 'storage', chunk_size: int = 1024 * 1024):
        """
        Инициализация файлового сервера
        
        :param storage_path: Путь к директории хранения файлов
        :param chunk_size: Размер чанка в байтах (по умолчанию 1MB)
        """
        self.storage_path = storage_path
        self.chunk_size = chunk_size
        self.ensure_storage_directory_exists()
        
    def ensure_storage_directory_exists(self) -> None:
        """Создает директорию для хранения файлов, если она не существует"""
        os.makedirs(self.storage_path, exist_ok=True)
    
    def get_file_path(self, filename: str) -> str:
        """
        Возвращает полный путь к файлу в хранилище
        
        :param filename: Имя файла
        :return: Полный путь к файлу
        """
        return os.path.join(self.storage_path, secure_filename(filename))
    
    def save_file_chunk(self, file_id: str, chunk_number: int, chunk_data: bytes) -> None:
        """
        Сохраняет чанк файла во временную директорию
        
        :param file_id: Идентификатор файла
        :param chunk_number: Номер чанка
        :param chunk_data: Данные чанка
        """
        temp_dir = os.path.join(self.storage_path, 'temp', file_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        chunk_path = os.path.join(temp_dir, f'chunk_{chunk_number}')
        with open(chunk_path, 'wb') as f:
            f.write(chunk_data)
    
    def assemble_file_from_chunks(self, file_id: str, filename: str, total_chunks: int) -> str:
        """
        Собирает файл из чанков и сохраняет его в хранилище
        
        :param file_id: Идентификатор файла
        :param filename: Имя файла
        :param total_chunks: Общее количество чанков
        :return: Путь к собранному файлу
        """
        temp_dir = os.path.join(self.storage_path, 'temp', file_id)
        file_path = self.get_file_path(filename)
        
        with open(file_path, 'wb') as output_file:
            for chunk_num in range(1, total_chunks + 1):
                chunk_path = os.path.join(temp_dir, f'chunk_{chunk_num}')
                with open(chunk_path, 'rb') as chunk_file:
                    output_file.write(chunk_file.read())
        
        # Очищаем временные чанки
        for chunk_num in range(1, total_chunks + 1):
            chunk_path = os.path.join(temp_dir, f'chunk_{chunk_num}')
            os.remove(chunk_path)
        os.rmdir(temp_dir)
        
        return file_path
    
    def delete_file(self, filename: str) -> bool:
        """
        Удаляет файл из хранилища
        
        :param filename: Имя файла
        :return: True, если файл был удален, False если файл не найден
        """
        file_path = self.get_file_path(filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def get_file_info(self, filename: str) -> Optional[Dict]:
        """
        Возвращает информацию о файле
        
        :param filename: Имя файла
        :return: Словарь с информацией о файле или None, если файл не найден
        """
        file_path = self.get_file_path(filename)
        if os.path.exists(file_path):
            return {
                'name': filename,
                'size': os.path.getsize(file_path),
                'modified': os.path.getmtime(file_path),
                'md5': self.calculate_file_md5(file_path)
            }
        return None
    
    def calculate_file_md5(self, file_path: str) -> str:
        """
        Вычисляет MD5 хеш файла
        
        :param file_path: Путь к файлу
        :return: MD5 хеш в виде строки
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def list_files(self) -> Dict[str, Dict]:
        """
        Возвращает список всех файлов в хранилище с их метаданными
        
        :return: Словарь с информацией о файлах
        """
        files = {}
        for filename in os.listdir(self.storage_path):
            file_path = os.path.join(self.storage_path, filename)
            if os.path.isfile(file_path):
                files[filename] = self.get_file_info(filename)
        return files
    
    def create_directory(self, dirname: str) -> bool:
        """
        Создает новую директорию в хранилище
        
        :param dirname: Имя директории
        :return: True, если директория создана, False если она уже существует
        """
        dir_path = self.get_file_path(dirname)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            return True
        return False
    
    def list_directory(self, dirname: str = '') -> Dict:
        """
        Возвращает содержимое директории
        
        :param dirname: Имя директории (относительно storage_path)
        :return: Словарь с содержимым директории
        """
        dir_path = self.get_file_path(dirname)
        if not os.path.isdir(dir_path):
            return {'error': 'Directory not found'}
        
        contents = {'files': [], 'directories': []}
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path):
                contents['files'].append(self.get_file_info(item))
            elif os.path.isdir(item_path):
                contents['directories'].append(item)
        
        return contents


app = Flask(__name__)
storage = FileStorageServer()

@app.route('/api/files', methods=['GET'])
def list_files():
    """Получить список всех файлов"""
    return jsonify(storage.list_files())

@app.route('/api/files/<path:filename>', methods=['GET'])
def download_file(filename):
    """Скачать файл"""
    file_path = storage.get_file_path(filename)
    if os.path.exists(file_path):
        return send_from_directory(storage.storage_path, filename, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/files/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    """Удалить файл"""
    if storage.delete_file(filename):
        return jsonify({'status': 'success'})
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/files/<path:filename>', methods=['POST'])
def upload_file(filename):
    """Загрузить файл (может быть чанком или целым файлом)"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Проверяем, является ли это чанком
    is_chunk = 'chunk_number' in request.form and 'total_chunks' in request.form
    file_id = request.form.get('file_id', hashlib.md5(filename.encode()).hexdigest())
    
    if is_chunk:
        chunk_number = int(request.form['chunk_number'])
        total_chunks = int(request.form['total_chunks'])
        storage.save_file_chunk(file_id, chunk_number, file.read())
        
        if chunk_number == total_chunks:
            storage.assemble_file_from_chunks(file_id, filename, total_chunks)
            return jsonify({'status': 'completed'})
        
        return jsonify({'status': 'chunk_uploaded', 'chunk_number': chunk_number})
    else:
        # Обычная загрузка файла
        file_path = storage.get_file_path(filename)
        file.save(file_path)
        return jsonify({'status': 'success'})

@app.route('/api/dirs', methods=['POST'])
def create_directory():
    """Создать директорию"""
    dirname = request.json.get('name')
    if not dirname:
        return jsonify({'error': 'Directory name is required'}), 400
    
    if storage.create_directory(dirname):
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Directory already exists'}), 400

@app.route('/api/dirs/<path:dirname>', methods=['GET'])
def list_directory(dirname):
    """Получить содержимое директории"""
    return jsonify(storage.list_directory(dirname))

@app.route('/api/files/<path:filename>/info', methods=['GET'])
def get_file_info(filename):
    """Получить информацию о файле"""
    info = storage.get_file_info(filename)
    if info:
        return jsonify(info)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

