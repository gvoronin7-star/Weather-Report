"""
Weather Report - приложение для отображения погоды
"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional

import requests


def load_dotenv(dotenv_path: str = ".env") -> None:
    """Загружает переменные окружения из .env файла"""
    if not os.path.exists(dotenv_path):
        return
    
    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                
                # Убираем кавычки если есть
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                os.environ[key] = value

# --- Константы ---
CACHE_FILE = "weather_cache.json"
GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
CACHE_MAX_AGE_HOURS = 3
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # экспоненциальная пауза в секундах

# --- Загрузка API ключа ---
def load_api_key() -> str:
    """Загружает API ключ из .env файла"""
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key or api_key == "your_openweathermap_api_key_here":
        raise ValueError("API_KEY не найден в .env файле. Добавьте ваш ключ в .env")
    return api_key


# --- Кэширование ---
def save_cache(data: dict) -> None:
    """Сохраняет данные в кэш"""
    cache_data = {
        "city": data.get("city", "Unknown"),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
        "temperature": data.get("temperature"),
        "feels_like": data.get("feels_like"),
        "humidity": data.get("humidity"),
        "pressure": data.get("pressure"),
        "wind_speed": data.get("wind_speed"),
        "wind_deg": data.get("wind_deg"),
        "visibility": data.get("visibility"),
        "clouds": data.get("clouds"),
        "description": data.get("description"),
        "fetched_at": datetime.now().isoformat()
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)


def load_cache() -> Optional[dict]:
    """Загружает данные из кэша"""
    if not os.path.exists(CACHE_FILE):
        return None
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def is_cache_valid(cache: dict) -> bool:
    """Проверяет, валиден ли кэш (младше 3 часов)"""
    if not cache or "fetched_at" not in cache:
        return False
    
    try:
        fetched_time = datetime.fromisoformat(cache["fetched_at"])
        age = datetime.now() - fetched_time
        return age < timedelta(hours=CACHE_MAX_AGE_HOURS)
    except (ValueError, TypeError):
        return False


# --- HTTP запросы с ретраями ---
def make_request_with_retry(url: str, params: dict, api_key: str) -> Optional[dict]:
    """
    Выполняет HTTP запрос с ретраями при ошибках
    Возвращает None при исчерпании попыток
    """
    params["appid"] = api_key
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
            elif response.status_code == 401:
                print("Ошибка авторизации. Проверьте API_KEY в .env")
                return None
            
            elif response.status_code == 404:
                print("Город не найден")
                return None
            
            elif response.status_code == 429:
                # Rate limit - делаем ретрай
                if attempt < MAX_RETRIES - 1:
                    print(f"Превышен лимит запросов. Повторная попытка через {RETRY_DELAYS[attempt]}с...")
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
            
            else:
                print(f"Ошибка HTTP: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                print(f"Превышен таймаут. Повторная попытка через {RETRY_DELAYS[attempt]}с...")
                time.sleep(RETRY_DELAYS[attempt])
                continue
            print("Сетевая ошибка: таймаут")
            return None
        
        except requests.exceptions.ConnectionError:
            if attempt < MAX_RETRIES - 1:
                print(f"Ошибка соединения. Повторная попытка через {RETRY_DELAYS[attempt]}с...")
                time.sleep(RETRY_DELAYS[attempt])
                continue
            print("Сетевая ошибка: не удалось подключиться к серверу")
            return None
        
        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {str(e)}")
            return None
    
    return None


# --- API функции ---
def get_coordinates(city: str, api_key: str) -> list[dict]:
    """
    Получает координаты города через Geocoding API
    Возвращает список возможных вариантов
    """
    params = {
        "q": city,
        "limit": 5,
        "lang": "ru"
    }
    
    result = make_request_with_retry(GEOCODING_URL, params, api_key)
    
    if not result:
        return []
    
    return result


def get_weather_by_coordinates(lat: float, lon: float, api_key: str) -> Optional[dict]:
    """
    Получает погоду по координатам через Current Weather API
    """
    params = {
        "lat": lat,
        "lon": lon,
        "units": "metric",
        "lang": "ru"
    }
    
    return make_request_with_retry(WEATHER_URL, params, api_key)


def parse_weather_response(data: dict, city_name: str = None) -> dict:
    """Парсит ответ API в удобный формат"""
    if not data:
        return None
    
    weather = data.get("weather", [{}])[0] if data.get("weather") else {}
    main = data.get("main", {})
    wind = data.get("wind", {})
    visibility = data.get("visibility", 10000)
    
    return {
        "city": city_name or data.get("name", "Unknown"),
        "lat": data.get("coord", {}).get("lat"),
        "lon": data.get("coord", {}).get("lon"),
        "temperature": main.get("temp"),
        "feels_like": main.get("feels_like"),
        "humidity": main.get("humidity"),
        "pressure": main.get("pressure"),  # hPa
        "description": weather.get("description", ""),
        "icon": weather.get("icon"),
        "wind_speed": wind.get("speed"),  # m/s
        "wind_deg": wind.get("deg"),
        "visibility": visibility,  # meters
        "clouds": data.get("clouds", {}).get("all"),  # %
    }


def get_weather_by_city(city: str, api_key: str, gui_mode: bool = False, parent_window=None) -> Optional[dict]:
    """
    Получает погоду по названию города
    При множественных результатах - запрашивает выбор у пользователя
    
    Args:
        city: Название города
        api_key: API ключ
        gui_mode: Если True - использует диалоговое окно для выбора города
        parent_window: Родительское окно tkinter для диалога
    """
    # Получаем координаты
    geo_results = get_coordinates(city, api_key)
    
    if not geo_results:
        if gui_mode and parent_window:
            from tkinter import messagebox
            messagebox.showinfo("Результат", "Город не найден", parent=parent_window)
        else:
            print("Город не найден")
        return None
    
    # Если несколько результатов - предложить выбор
    selected = None
    
    if len(geo_results) > 1:
        if gui_mode and parent_window:
            # GUI режим - используем диалог
            from tkinter import messagebox
            import tkinter as tk
            
            # Формируем список вариантов
            choices = []
            for result in geo_results:
                state = result.get("state", "")
                country = result.get("country", "")
                location = country
                if state:
                    location = f"{state}, {country}"
                choices.append(f"{result.get('name')}, {location}")
            
            # Показываем диалог выбора
            dialog = tk.Toplevel(parent_window)
            dialog.title("Выберите город")
            dialog.geometry("350x300")
            dialog.transient(parent_window)
            dialog.grab_set()
            
            tk.Label(dialog, text=f"Найдено несколько городов '{city}':", 
                    font=("Arial", 10)).pack(pady=10)
            
            var = tk.IntVar(value=0)
            for i, choice in enumerate(choices):
                rb = tk.Radiobutton(dialog, text=choice, variable=var, value=i)
                rb.pack(anchor="w", padx=20)
            
            result = [None]
            
            def on_select():
                result[0] = var.get()
                dialog.destroy()
            
            def on_cancel():
                result[0] = -1
                dialog.destroy()
            
            tk.Button(dialog, text="Выбрать", command=on_select).pack(pady=10)
            tk.Button(dialog, text="Отмена", command=on_cancel).pack()
            
            dialog.wait_window()
            
            if result[0] == -1 or result[0] is None:
                return None
            
            selected = geo_results[result[0]]
            
        else:
            # CLI режим
            print(f"Найдено несколько городов с названием '{city}':")
            for i, result in enumerate(geo_results, 1):
                state = result.get("state", "")
                country = result.get("country", "")
                location = f"{country}"
                if state:
                    location = f"{state}, {country}"
                print(f"  {i}. {result.get('name')}, {location}")
            
            while True:
                try:
                    choice = input("Выберите номер (1-{0}): ".format(len(geo_results)))
                    idx = int(choice) - 1
                    if 0 <= idx < len(geo_results):
                        selected = geo_results[idx]
                        break
                    else:
                        print("Некорректный номер. Попробуйте снова.")
                except ValueError:
                    print("Введите число.")
    else:
        selected = geo_results[0]
    
    if not selected:
        return None
    
    lat = selected.get("lat")
    lon = selected.get("lon")
    city_name = selected.get("name")
    
    # Получаем погоду
    weather_data = get_weather_by_coordinates(lat, lon, api_key)
    
    if not weather_data:
        return None
    
    return parse_weather_response(weather_data, city_name)


def get_weather_by_coords_input(lat: float, lon: float, api_key: str) -> Optional[dict]:
    """Получает погоду по введённым координатам"""
    weather_data = get_weather_by_coordinates(lat, lon, api_key)
    
    if not weather_data:
        return None
    
    return parse_weather_response(weather_data)


def format_weather_output(weather: dict) -> str:
    """Форматирует данные о погоде для вывода"""
    if not weather:
        return "Нет данных о погоде"
    
    temp = weather.get("temperature")
    desc = weather.get("description", "")
    city = weather.get("city", "Unknown")
    
    if temp is not None:
        return f"Погода в {city}: {temp}°C, {desc}"
    return f"Не удалось получить данные о погоде в {city}"


# --- CLI интерфейс ---
def run_cli():
    """Запускает CLI интерфейс"""
    try:
        api_key = load_api_key()
    except ValueError as e:
        print(f"Ошибка: {e}")
        return
    
    print("=" * 50)
    print("Weather Report - Узнай погоду в любом городе!")
    print("=" * 50)
    
    while True:
        print("\nМеню:")
        print("1 - Поиск по городу")
        print("2 - Поиск по координатам")
        print("0 - Выход")
        
        choice = input("Выберите режим: ").strip()
        
        if choice == "0":
            print("До свидания!")
            break
        
        elif choice == "1":
            city = input("Введите название города: ").strip()
            if not city:
                print("Введите название города")
                continue
            
            # Пробуем получить погоду
            weather = get_weather_by_city(city, api_key)
            
            if weather:
                print(format_weather_output(weather))
                save_cache(weather)
            else:
                # Предложить использовать кэш
                cache = load_cache()
                if cache and is_cache_valid(cache):
                    use_cache = input("Использовать данные из кэша? (д/н): ").strip().lower()
                    if use_cache in ("д", "y", "yes", "да"):
                        print(format_weather_output(cache))
                else:
                    print("Нет доступных данных в кэше")
        
        elif choice == "2":
            try:
                lat_input = input("Введите широту (lat): ").strip()
                lon_input = input("Введите долготу (lon): ").strip()
                
                lat = float(lat_input.replace(",", "."))
                lon = float(lon_input.replace(",", "."))
                
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    print("Координаты вне допустимого диапазона")
                    continue
                
                weather = get_weather_by_coords_input(lat, lon, api_key)
                
                if weather:
                    print(format_weather_output(weather))
                    save_cache(weather)
                else:
                    # Предложить использовать кэш
                    cache = load_cache()
                    if cache and is_cache_valid(cache):
                        use_cache = input("Использовать данные из кэша? (д/н): ").strip().lower()
                        if use_cache in ("д", "y", "yes", "да"):
                            print(format_weather_output(cache))
            
            except ValueError:
                print("Некорректный формат координат")
        
        else:
            print("Некорректный выбор. Попробуйте снова.")


# --- GUI интерфейс ---
def run_gui():
    """Запускает GUI интерфейс с использованием tkinter"""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as e:
        print(f"Ошибка: tkinter не доступен - {e}")
        return
    
    try:
        api_key = load_api_key()
    except ValueError as e:
        messagebox.showerror("Ошибка", str(e))
        return
    
    root = tk.Tk()
    root.title("Weather Report")
    root.geometry("500x680")
    root.resizable(True, True)
    root.minsize(400, 500)
    
    # Стиль
    style = ttk.Style()
    style.configure("TButton", padding=6)
    style.configure("TLabel", font=("Arial", 10))
    
    # Заголовок
    header = tk.Label(root, text="Weather Report", font=("Arial", 18, "bold"))
    header.pack(pady=10)
    
    # Переменные
    city_var = tk.StringVar()
    lat_var = tk.StringVar()
    lon_var = tk.StringVar()
    
    # Переменные для отображения результатов
    temp_var = tk.StringVar()
    feels_like_var = tk.StringVar()
    humidity_var = tk.StringVar()
    pressure_var = tk.StringVar()
    wind_var = tk.StringVar()
    visibility_var = tk.StringVar()
    clouds_var = tk.StringVar()
    description_var = tk.StringVar()
    city_name_var = tk.StringVar()
    
    # Фрейм для ввода по городу
    frame_city = tk.LabelFrame(root, text="По городу", padx=10, pady=10)
    frame_city.pack(fill="x", padx=10, pady=5)
    
    tk.Label(frame_city, text="Город:").pack(anchor="w")
    city_entry = tk.Entry(frame_city, textvariable=city_var, width=40)
    city_entry.pack(pady=5)
    
    def search_by_city():
        city = city_var.get().strip()
        if not city:
            city_name_var.set("Введите название города")
            return
        
        try:
            weather = get_weather_by_city(city, api_key, gui_mode=True, parent_window=root)
            if weather:
                update_weather_display(weather)
                save_cache(weather)
            else:
                # Проверяем кэш
                cache = load_cache()
                if cache and is_cache_valid(cache):
                    update_weather_display(cache)
                    city_name_var.set(cache.get("city", "") + " (из кэша)")
                else:
                    clear_weather_display()
                    city_name_var.set("Город не найден")
        except Exception as e:
            clear_weather_display()
            city_name_var.set(f"Ошибка: {str(e)}")
    
    ttk.Button(frame_city, text="Узнать погоду", command=search_by_city).pack()
    
    # Фрейм для ввода по координатам
    frame_coords = tk.LabelFrame(root, text="По координатам", padx=10, pady=10)
    frame_coords.pack(fill="x", padx=10, pady=5)
    
    coords_frame = tk.Frame(frame_coords)
    coords_frame.pack()
    
    tk.Label(coords_frame, text="Широта:").grid(row=0, column=0, padx=5)
    lat_entry = tk.Entry(coords_frame, textvariable=lat_var, width=12)
    lat_entry.grid(row=0, column=1, padx=5)
    
    tk.Label(coords_frame, text="Долгота:").grid(row=0, column=2, padx=5)
    lon_entry = tk.Entry(coords_frame, textvariable=lon_var, width=12)
    lon_entry.grid(row=0, column=3, padx=5)
    
    def search_by_coords():
        try:
            lat = float(lat_var.get().replace(",", "."))
            lon = float(lon_var.get().replace(",", "."))
            
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                city_name_var.set("Координаты вне допустимого диапазона")
                return
            
            weather = get_weather_by_coords_input(lat, lon, api_key)
            if weather:
                update_weather_display(weather)
                save_cache(weather)
            else:
                cache = load_cache()
                if cache and is_cache_valid(cache):
                    update_weather_display(cache)
                    city_name_var.set(cache.get("city", "") + " (из кэша)")
                else:
                    clear_weather_display()
                    city_name_var.set("Не удалось получить данные")
        except ValueError:
            clear_weather_display()
            city_name_var.set("Некорректный формат координат")
        except Exception as e:
            clear_weather_display()
            city_name_var.set(f"Ошибка: {str(e)}")
    
    ttk.Button(frame_coords, text="Узнать погоду", command=search_by_coords).pack(pady=5)
    
    # Фрейм результатов с возможностью скролла
    canvas = tk.Canvas(root, highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, padx=10, pady=10)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Упаковка скролла
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)

    # Используем scrollable_frame для всех элементов результата
    frame_result = tk.LabelFrame(scrollable_frame, text="Погода", padx=10, pady=5)
    frame_result.pack(fill="both", expand=True, padx=5, pady=5)

    # Название города
    tk.Label(frame_result, textvariable=city_name_var, font=("Arial", 14, "bold"), 
             fg="darkblue").pack(pady=(0, 5))

    # Описание
    tk.Label(frame_result, textvariable=description_var, font=("Arial", 10, "italic"),
             fg="gray").pack()
    
    # Температура (крупно)
    tk.Label(frame_result, textvariable=temp_var, font=("Arial", 32, "bold"), 
             fg="red").pack(pady=5)

    # Сетка дополнительных параметров (компактная)
    params_frame = tk.Frame(frame_result)
    params_frame.pack(pady=5)

    # Ощущается как
    tk.Label(params_frame, text="Ощущается как:", font=("Arial", 8)).grid(
        row=0, column=0, sticky="w", padx=5, pady=2)
    tk.Label(params_frame, textvariable=feels_like_var, font=("Arial", 9, "bold")).grid(
        row=0, column=1, sticky="w", padx=5, pady=2)

    # Влажность
    tk.Label(params_frame, text="Влажность:", font=("Arial", 8)).grid(
        row=1, column=0, sticky="w", padx=5, pady=2)
    tk.Label(params_frame, textvariable=humidity_var, font=("Arial", 9, "bold")).grid(
        row=1, column=1, sticky="w", padx=5, pady=2)

    # Давление
    tk.Label(params_frame, text="Давление:", font=("Arial", 8)).grid(
        row=2, column=0, sticky="w", padx=5, pady=2)
    tk.Label(params_frame, textvariable=pressure_var, font=("Arial", 9, "bold")).grid(
        row=2, column=1, sticky="w", padx=5, pady=2)

    # Ветер
    tk.Label(params_frame, text="Ветер:", font=("Arial", 8)).grid(
        row=3, column=0, sticky="w", padx=5, pady=2)
    tk.Label(params_frame, textvariable=wind_var, font=("Arial", 9, "bold")).grid(
        row=3, column=1, sticky="w", padx=5, pady=2)

    # Видимость
    tk.Label(params_frame, text="Видимость:", font=("Arial", 8)).grid(
        row=4, column=0, sticky="w", padx=5, pady=2)
    tk.Label(params_frame, textvariable=visibility_var, font=("Arial", 9, "bold")).grid(
        row=4, column=1, sticky="w", padx=5, pady=2)

    # Облачность
    tk.Label(params_frame, text="Облачность:", font=("Arial", 8)).grid(
        row=5, column=0, sticky="w", padx=5, pady=2)
    tk.Label(params_frame, textvariable=clouds_var, font=("Arial", 9, "bold")).grid(
        row=5, column=1, sticky="w", padx=5, pady=2)

    def update_weather_display(weather: dict):
        """Обновляет отображение данных о погоде"""
        city_name_var.set(weather.get("city", ""))
        
        temp = weather.get("temperature")
        temp_var.set(f"{temp}°C" if temp is not None else "--")
        
        feels = weather.get("feels_like")
        feels_like_var.set(f"{feels}°C" if feels is not None else "--")
        
        humidity = weather.get("humidity")
        humidity_var.set(f"{humidity}%" if humidity is not None else "--")
        
        pressure = weather.get("pressure")
        pressure_var.set(f"{pressure} гПа" if pressure is not None else "--")
        
        wind_speed = weather.get("wind_speed")
        wind_deg = weather.get("wind_deg")
        if wind_speed is not None:
            wind_str = f"{wind_speed} м/с"
            if wind_deg is not None:
                directions = ["С", "С-В", "В", "Ю-В", "Ю", "Ю-З", "З", "С-З"]
                idx = round(wind_deg / 45) % 8
                wind_str += f" ({directions[idx]})"
            wind_var.set(wind_str)
        else:
            wind_var.set("--")
        
        visibility = weather.get("visibility")
        if visibility is not None:
            visibility_var.set(f"{visibility/1000:.1f} км")
        else:
            visibility_var.set("--")
        
        clouds = weather.get("clouds")
        clouds_var.set(f"{clouds}%" if clouds is not None else "--")
        
        description_var.set(weather.get("description", "").capitalize())
    
    def clear_weather_display():
        """Очищает отображение погоды"""
        city_name_var.set("")
        temp_var.set("")
        feels_like_var.set("")
        humidity_var.set("")
        pressure_var.set("")
        wind_var.set("")
        visibility_var.set("")
        clouds_var.set("")
        description_var.set("")
    
    # Кнопка выхода (в scrollable_frame, не в frame_result)
    ttk.Button(scrollable_frame, text="Выход", command=root.quit).pack(pady=10)
    
    root.mainloop()


# --- Главная точка входа ---
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        run_gui()
    else:
        # Спросить какой интерфейс использовать
        print("Выберите интерфейс:")
        print("1 - CLI (консольный)")
        print("2 - GUI (графический)")
        
        choice = input("Ваш выбор (1/2): ").strip()
        
        if choice == "2":
            run_gui()
        else:
            run_cli()
