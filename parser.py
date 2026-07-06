import json
import time
import random
import re
import logging
from seleniumbase import Driver

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def extract_contact_id(url: str) -> str | None:
    if not url:
        return None
    patterns = [
        r'/(?:chat|dialog|im|peer|contact)/([A-Za-z0-9_-]+)',
        r'[?&](?:id|peer|user|chat_id|contact_id)=([A-Za-z0-9_-]+)',
        r'#(?:/)?(?:chat|dialog|im)/([A-Za-z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    clean = url.split('?')[0].split('#')[0].rstrip('/')
    parts = [p for p in clean.split('/') if p]
    if parts:
        last = parts[-1]
        if len(last) >= 3 and (last.isdigit() or last.isalnum()):
            return last
    return None


def get_or_create_driver(profile_dir="/home/akozh/PycharmProjects/Maxer/browser_profile", existing_driver=None):
    """Возвращает драйвер. Если передан — использует его, если нет — создаёт новый."""
    if existing_driver:
        return existing_driver, False
    return Driver(uc=True, headless=False, user_data_dir=profile_dir), True


def safe_quit_driver(driver, should_quit):
    """Закрывает браузер только если мы его создавали сами."""
    if should_quit and driver:
        try:
            driver.quit()
        except:
            pass


# ==================== ФУНКЦИИ ====================

def create_max_contacts_database(
    profile_dir: str = "/home/akozh/PycharmProjects/Maxer/browser_profile",
    output_file: str = "max_contacts_with_ids.json",
    max_scrolls: int = 50,
    driver=None
):
    logger.info("=== Запуск создания базы контактов MAX ===")

    existing_results = []
    processed_names = set()
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing_results = json.load(f)
            processed_names = {c["name"] for c in existing_results}
    except FileNotFoundError:
        logger.info("Файл базы не найден — создаём новую")

    driver_instance, should_quit = get_or_create_driver(profile_dir, driver)

    try:
        driver_instance.get("https://web.max.ru")
        driver_instance.wait_for_element("button.cell", timeout=25)
        logger.info("Список чатов загружен")

        valid_contacts = []
        seen = set(processed_names)
        last_height = driver_instance.execute_script("return document.body.scrollHeight")
        no_change_count = 0

        while no_change_count < 3 and len(seen) < 5000:
            chat_elements = driver_instance.find_elements("button.cell")
            for chat in chat_elements:
                try:
                    name = chat.find_element("css selector", ".name.svelte-1riu5uh").text.strip()
                    if name and len(name) > 1 and "Вход" not in name and "Поиск" not in name and name not in seen:
                        has_avatar = bool(chat.find_elements("css selector", "img, .avatar"))
                        valid_contacts.append({"name": name, "has_avatar": has_avatar})
                        seen.add(name)
                except:
                    continue

            driver_instance.execute_script("window.scrollBy(0, 900);")
            time.sleep(1.2)
            new_height = driver_instance.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_change_count += 1
            else:
                no_change_count = 0
                last_height = new_height

        logger.info(f"Найдено {len(valid_contacts)} новых контактов")

        new_results = []
        for idx, contact in enumerate(valid_contacts, 1):
            name = contact["name"]
            logger.info(f"[{idx}/{len(valid_contacts)}] Обрабатываем: {name}")
            try:
                name_esc = name.replace("'", "\\'").replace('"', '\\"')
                xpath = f"//button[contains(@class,'cell')][.//span[contains(@class,'name') and contains(normalize-space(.), '{name_esc}')]]"
                button = driver_instance.find_element("xpath", xpath)

                old_url = driver_instance.current_url
                button.click()

                for _ in range(40):
                    time.sleep(0.5)
                    if driver_instance.current_url != old_url:
                        break
                else:
                    driver_instance.back()
                    continue

                new_url = driver_instance.current_url
                contact_id = extract_contact_id(new_url)

                new_results.append({
                    "name": name,
                    "id": contact_id,
                    "chat_url": new_url
                })
                logger.info(f"→ chat_url: {new_url}")

                driver_instance.back()
                driver_instance.wait_for_element("button.cell", timeout=10)
                time.sleep(random.uniform(1.0, 2.5))

            except Exception as e:
                logger.error(f"Ошибка с '{name}': {e}")
                try:
                    driver_instance.back()
                except:
                    pass

        final_results = existing_results + new_results
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)

        logger.info(f"=== Готово! Всего контактов: {len(final_results)} ===")
        return {"status": "успешно", "всего_в_базе": len(final_results)}

    finally:
        safe_quit_driver(driver_instance, should_quit)


def send_message_to_contact(contact_name: str, message: str, json_file="max_contacts_with_ids.json",
                            profile_dir="/home/akozh/PycharmProjects/Maxer/browser_profile", driver=None):
    logger.info(f"=== Отправка сообщения: {contact_name} ===")

    with open(json_file, "r", encoding="utf-8") as f:
        contacts = json.load(f)

    contact = next((c for c in contacts if c["name"].lower() == contact_name.lower() or "избранное" in c["name"].lower()), None)
    if not contact:
        return {"status": "ошибка", "причина": "Контакт не найден"}

    chat_url = contact.get("chat_url") or f"https://web.max.ru/{contact.get('id', '')}"

    driver_instance, should_quit = get_or_create_driver(profile_dir, driver)

    try:
        driver_instance.get(chat_url)
        time.sleep(2.5)

        input_el = driver_instance.wait_for_element("div.contenteditable.svelte-1k31az8", timeout=10)
        input_el.click()
        time.sleep(0.6)

        driver_instance.execute_script("""
            const editor = arguments[0];
            editor.focus();
            const sel = window.getSelection();
            sel.selectAllChildren(editor);
            sel.deleteFromDocument();
            document.execCommand('insertText', false, arguments[1]);
            editor.dispatchEvent(new InputEvent('input', {bubbles: true}));
        """, input_el, message)

        from selenium.webdriver.common.keys import Keys
        input_el.send_keys(Keys.ENTER)
        time.sleep(1.5)

        logger.info("✅ Сообщение отправлено")
        return {"status": "успешно", "chat_url": chat_url}

    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        return {"status": "ошибка", "причина": str(e)}
    finally:
        safe_quit_driver(driver_instance, should_quit)


def get_last_messages(chat_name: str, count: int = 5, profile_dir="/home/akozh/PycharmProjects/Maxer/browser_profile", driver=None):
    logger.info(f"Читаем последние {count} сообщений из: {chat_name}")

    with open("max_contacts_with_ids.json", "r", encoding="utf-8") as f:
        contacts = json.load(f)

    contact = next((c for c in contacts if c["name"].lower() == chat_name.lower()), None)
    if not contact:
        return []

    chat_url = contact.get("chat_url") or f"https://web.max.ru/{contact.get('id', '')}"

    driver_instance, should_quit = get_or_create_driver(profile_dir, driver)

    try:
        driver_instance.get(chat_url)
        time.sleep(3)

        bubbles = driver_instance.find_elements("css selector", "div[data-bubbles-variant]")
        last_bubbles = bubbles[-count:] if len(bubbles) > count else bubbles

        messages = []
        for bubble in last_bubbles:
            try:
                variant = bubble.get_attribute("data-bubbles-variant") or ""
                is_outgoing = "outgoing" in variant
                text = bubble.find_element("css selector", "span.text.svelte-1htnb3l").text.strip()
                try:
                    msg_time = bubble.find_element("css selector", "span.meta .text").text.strip()
                except:
                    msg_time = ""

                messages.append({
                    "sender": "Ты" if is_outgoing else chat_name,
                    "text": text,
                    "time": msg_time,
                    "is_outgoing": is_outgoing
                })
            except:
                continue

        return messages
    finally:
        safe_quit_driver(driver_instance, should_quit)


# ==================== ТЕСТ ====================

if __name__ == "__main__":
    print("🚀 === ТЕСТ ПАРСЕРА МАКСЕР (ОДИН БРАУЗЕР) ===\n")
    errors = []
    driver = None

    try:
        driver = Driver(uc=True, headless=False, user_data_dir="/home/akozh/PycharmProjects/Maxer/browser_profile")

        # 0. База контактов
        print("[0] Создание базы контактов...")
        try:
            result = create_max_contacts_database(driver=driver)
            print(f"✓ Успешно ({result['всего_в_базе']} контактов)")
        except Exception as e:
            errors.append(("create_max_contacts_database", str(e)))
            print(f"✗ {e}")

        time.sleep(2)

        # 1. Отправка
        print("\n[1] Отправка сообщения в Избранное...")
        try:
            result = send_message_to_contact("Избранное", "Тест из одного браузера", driver=driver)
            print("Результат:", result)
        except Exception as e:
            errors.append(("send_message_to_contact", str(e)))
            print(f"✗ {e}")

        time.sleep(2)

        # 2. Чтение
        print("\n[2] Чтение последних сообщений...")
        try:
            messages = get_last_messages("Избранное", count=5, driver=driver)
            print(f"✓ Получено {len(messages)} сообщений")
            for m in messages:
                print(m)
        except Exception as e:
            errors.append(("get_last_messages", str(e)))
            print(f"✗ {e}")

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

    print("\n" + "="*55)
    if errors:
        print("❌ ОБНАРУЖЕННЫЕ ОШИБКИ:")
        for name, err in errors:
            print(f"  • {name}: {err}")
    else:
        print("✅ Все тесты прошли успешно!")
    print("="*55)