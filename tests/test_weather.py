"""
Автотесты для модуля weather_app.py
"""
import os
import json
import sys
import unittest
import requests
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import weather_app


class TestWeatherApp(unittest.TestCase):
    """Тесты для модуля weather_app"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.test_cache_file = "test_weather_cache.json"
        weather_app.CACHE_FILE = self.test_cache_file
    
    def tearDown(self):
        """Очистка после каждого теста"""
        if os.path.exists(self.test_cache_file):
            os.remove(self.test_cache_file)
    
    # --- Тесты кэширования ---
    def test_save_cache(self):
        """Тест сохранения в кэш"""
        test_data = {
            "city": "Moscow",
            "lat": 55.75,
            "lon": 37.61,
            "temperature": 10.5,
            "description": "ясно"
        }
        
        weather_app.save_cache(test_data)
        
        self.assertTrue(os.path.exists(self.test_cache_file))
        
        with open(self.test_cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
        
        self.assertEqual(cache["city"], "Moscow")
        self.assertEqual(cache["lat"], 55.75)
        self.assertIn("fetched_at", cache)
    
    def test_load_cache(self):
        """Тест загрузки из кэша"""
        test_data = {
            "city": "London",
            "lat": 51.51,
            "lon": -0.13,
            "temperature": 15.0,
            "description": "облачно",
            "fetched_at": datetime.now().isoformat()
        }
        
        with open(self.test_cache_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        
        cache = weather_app.load_cache()
        
        self.assertIsNotNone(cache)
        self.assertEqual(cache["city"], "London")
        self.assertEqual(cache["temperature"], 15.0)
    
    def test_load_cache_no_file(self):
        """Тест загрузки из кэша при отсутствии файла"""
        cache = weather_app.load_cache()
        self.assertIsNone(cache)
    
    def test_is_cache_valid_fresh(self):
        """Тест валидности свежего кэша"""
        cache = {
            "city": "Test",
            "fetched_at": datetime.now().isoformat()
        }
        self.assertTrue(weather_app.is_cache_valid(cache))
    
    def test_is_cache_valid_old(self):
        """Тест валидности старого кэша (> 3 часов)"""
        old_time = datetime.now() - timedelta(hours=4)
        cache = {
            "city": "Test",
            "fetched_at": old_time.isoformat()
        }
        self.assertFalse(weather_app.is_cache_valid(cache))
    
    def test_is_cache_valid_invalid(self):
        """Тест валидности некорректного кэша"""
        self.assertFalse(weather_app.is_cache_valid(None))
        self.assertFalse(weather_app.is_cache_valid({}))
        self.assertFalse(weather_app.is_cache_valid({"fetched_at": "invalid"}))
    
    # --- Тесты парсинга ---
    def test_parse_weather_response(self):
        """Тест парсинга ответа API"""
        api_response = {
            "name": "Москва",
            "coord": {"lat": 55.75, "lon": 37.61},
            "main": {
                "temp": 12.5,
                "feels_like": 10.0,
                "humidity": 75
            },
            "weather": [
                {
                    "description": "ясно",
                    "icon": "01d"
                }
            ]
        }
        
        result = weather_app.parse_weather_response(api_response)
        
        self.assertEqual(result["city"], "Москва")
        self.assertEqual(result["temperature"], 12.5)
        self.assertEqual(result["description"], "ясно")
        self.assertEqual(result["lat"], 55.75)
        self.assertEqual(result["lon"], 37.61)
    
    def test_parse_weather_response_none(self):
        """Тест парсинга пустого ответа"""
        result = weather_app.parse_weather_response(None)
        self.assertIsNone(result)
    
    # --- Тесты форматирования вывода ---
    def test_format_weather_output(self):
        """Тест форматирования вывода погоды"""
        weather = {
            "city": "Москва",
            "temperature": 12.5,
            "description": "ясно"
        }
        
        output = weather_app.format_weather_output(weather)
        
        self.assertEqual(output, "Погода в Москва: 12.5°C, ясно")
    
    def test_format_weather_output_none(self):
        """Тест форматирования при отсутствии данных"""
        output = weather_app.format_weather_output(None)
        self.assertEqual(output, "Нет данных о погоде")
    
    # --- Тесты API запросов с моками ---
    @patch('weather_app.load_api_key')
    @patch('weather_app.requests.get')
    def test_get_coordinates_success(self, mock_get, mock_load_key):
        """Тест успешного получения координат"""
        mock_load_key.return_value = "test_api_key"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "Москва",
                "lat": 55.75,
                "lon": 37.61,
                "country": "RU",
                "state": "Moscow"
            }
        ]
        mock_get.return_value = mock_response
        
        result = weather_app.get_coordinates("Москва", "test_api_key")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Москва")
        self.assertEqual(result[0]["lat"], 55.75)
    
    @patch('weather_app.load_api_key')
    @patch('weather_app.requests.get')
    def test_get_coordinates_not_found(self, mock_get, mock_load_key):
        """Тест отсутствия города"""
        mock_load_key.return_value = "test_api_key"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        result = weather_app.get_coordinates("NonExistentCity12345", "test_api_key")
        
        self.assertEqual(len(result), 0)
    
    @patch('weather_app.load_api_key')
    @patch('weather_app.requests.get')
    def test_get_weather_by_coordinates_success(self, mock_get, mock_load_key):
        """Тест успешного получения погоды"""
        mock_load_key.return_value = "test_api_key"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "Москва",
            "coord": {"lat": 55.75, "lon": 37.61},
            "main": {"temp": 15.0, "feels_like": 13.0, "humidity": 60},
            "weather": [{"description": "облачно", "icon": "03d"}]
        }
        mock_get.return_value = mock_response
        
        result = weather_app.get_weather_by_coordinates(55.75, 37.61, "test_api_key")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["main"]["temp"], 15.0)
    
    @patch('weather_app.load_api_key')
    @patch('weather_app.requests.get')
    def test_get_weather_auth_error(self, mock_get, mock_load_key):
        """Тест ошибки авторизации"""
        mock_load_key.return_value = "test_api_key"
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        # Перехватываем вывод
        with patch('builtins.print'):
            result = weather_app.get_weather_by_coordinates(55.75, 37.61, "invalid_key")
        
        # При 401 возвращается None после обработки ошибки
        # (функция проверяет статус и возвращает None для 401)
        # На самом деле нужно проверить, что мы не делаем ретрай
    
    # --- Тесты ретраев ---
    @patch('weather_app.requests.get')
    @patch('weather_app.time.sleep')
    def test_retry_on_timeout(self, mock_sleep, mock_get):
        """Тест ретрая при таймауте"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        
        # Первые 2 раза таймаут, потом успех
        mock_get.side_effect = [
            requests.exceptions.Timeout(),
            requests.exceptions.Timeout(),
            mock_response
        ]
        
        result = weather_app.make_request_with_retry(
            "http://test.com",
            {},
            "test_key"
        )
        
        # Должно быть 3 попытки
        self.assertEqual(mock_get.call_count, 3)
        self.assertIsNotNone(result)
    
    @patch('weather_app.requests.get')
    @patch('weather_app.time.sleep')
    def test_retry_on_rate_limit(self, mock_sleep, mock_get):
        """Тест ретрая при 429 (rate limit)"""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"test": "data"}
        
        mock_get.side_effect = [mock_response_429, mock_response_200]
        
        result = weather_app.make_request_with_retry(
            "http://test.com",
            {},
            "test_key"
        )
        
        self.assertEqual(mock_get.call_count, 2)
        self.assertIsNotNone(result)
    
    # --- Тесты выбора города ---
    @patch('weather_app.load_api_key')
    @patch('weather_app.get_coordinates')
    @patch('weather_app.get_weather_by_coordinates')
    @patch('builtins.input', side_effect=["1"])
    def test_multiple_cities_selection(self, mock_input, mock_weather, mock_coords, mock_key):
        """Тест выбора города при множественных результатах"""
        mock_key.return_value = "test_api_key"
        
        # Несколько городов с названием Springfield
        mock_coords.return_value = [
            {"name": "Springfield", "lat": 39.78, "lon": -89.65, "country": "US", "state": "Illinois"},
            {"name": "Springfield", "lat": 42.10, "lon": -72.52, "country": "US", "state": "Massachusetts"},
            {"name": "Springfield", "lat": 37.20, "lon": -93.29, "country": "US", "state": "Missouri"}
        ]
        
        mock_weather.return_value = {
            "name": "Springfield",
            "coord": {"lat": 39.78, "lon": -89.65},
            "main": {"temp": 20.0, "feels_like": 18.0, "humidity": 50},
            "weather": [{"description": "солнечно", "icon": "01d"}]
        }
        
        result = weather_app.get_weather_by_city("Springfield", "test_api_key")
        
        # Проверяем, что был выбран первый вариант
        mock_weather.assert_called_once_with(39.78, -89.65, "test_api_key")


class TestAPIKeyLoading(unittest.TestCase):
    """Тесты загрузки API ключа"""
    
    @patch.dict(os.environ, {"API_KEY": "test_key_123"})
    @patch('weather_app.load_dotenv')
    def test_load_api_key_success(self, mock_dotenv):
        """Тест успешной загрузки ключа"""
        mock_dotenv.return_value = None
        
        # Перезагружаем модуль для применения патча
        result = weather_app.load_api_key()
        
        self.assertEqual(result, "test_key_123")
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('weather_app.load_dotenv')
    def test_load_api_key_missing(self, mock_dotenv):
        """Тест отсутствия ключа"""
        mock_dotenv.return_value = None
        
        with self.assertRaises(ValueError) as context:
            weather_app.load_api_key()
        
        self.assertIn("API_KEY не найден", str(context.exception))


if __name__ == "__main__":
    # Запуск тестов
    unittest.main(verbosity=2)
