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
    # фоллбэк
    clean = url.split('?')[0].split('#')[0].rstrip('/')
    parts = [p for p in clean.split('/') if p]
    if parts:
        last = parts[-1]
        if len(last) >= 3 and (last.isdigit() or last.isalnum()):
            return last
    return None


def create_max_contacts_database(
    profile_dir: str = "/home/akozh/PycharmProjects/Maxer/browser_profile",
    output_file: str = "max_contacts_with_ids.json",
    max_scrolls: int = 50
):
    """
    Полностью сканирует все контакты в MAX Web.
    Кликает по каждому, получает ID из URL и сохраняет в JSON.
    Поддерживает возобновление (не обрабатывает уже сохранённые контакты).
    """
    logger.info("=== Запуск создания базы контактов MAX ===")

    # Загружаем уже обработанные контакты (для возобновления)
    existing_results = []
    processed_names = set()
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing_results = json.load(f)
            processed_names = {c["name"] for c in existing_results}
            logger.info(f"Загружено {len(existing_results)} уже обработанных контактов")
    except FileNotFoundError:
        logger.info("Файл базы не найден — создаём новую")

    with Driver(uc=True, headless=False, user_data_dir=profile_dir) as driver:
        driver.get("https://web.max.ru")
        driver.wait_for_element("button.cell", timeout=25)
        logger.info("Список чатов загружен")

        # === Полностью прокручиваем список ===
        valid_contacts = []
        seen = set(processed_names)  # уже обработанные пропускаем
        last_height = driver.execute_script("return document.body.scrollHeight")
        no_change_count = 0

        while no_change_count < 3 and len(seen) < 5000:  # защита от бесконечного цикла
            chat_elements = driver.find_elements("button.cell")

            for chat in chat_elements:
                try:
                    name_el = chat.find_element("css selector", ".name.svelte-1riu5uh")
                    name = name_el.text.strip()

                    if (name and len(name) > 1 and
                        "Вход" not in name and "Поиск" not in name and name not in seen):

                        try:
                            chat.find_element("css selector", "img, .avatar")
                            has_avatar = True
                        except:
                            has_avatar = False

                        valid_contacts.append({"name": name, "has_avatar": has_avatar})
                        seen.add(name)
                except:
                    continue

            driver.execute_script("window.scrollBy(0, 900);")
            time.sleep(1.2)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                no_change_count += 1
            else:
                no_change_count = 0
                last_height = new_height

        logger.info(f"Найдено {len(valid_contacts)} новых контактов для обработки")

        # === Обрабатываем каждый контакт ===
        new_results = []
        for idx, contact in enumerate(valid_contacts, 1):
            name = contact["name"]
            logger.info(f"[{idx}/{len(valid_contacts)}] Обрабатываем: {name}")

            try:
                name_esc = name.replace("'", "\\'").replace('"', '\\"')
                xpath = (
                    f"//button[contains(@class,'cell')]"
                    f"[.//span[contains(@class,'name') and contains(normalize-space(.), '{name_esc}')]]"
                )
                button = driver.find_element("xpath", xpath)

                old_url = driver.current_url
                button.click()

                changed = False
                for _ in range(40):
                    time.sleep(0.5)
                    if driver.current_url != old_url:
                        changed = True
                        break

                if not changed:
                    logger.warning(f"URL не изменился для {name}")
                    driver.back()
                    time.sleep(1)
                    continue

                new_url = driver.current_url
                contact_id = extract_contact_id(new_url)

                new_results.append({
                    "name": name,
                    "id": contact_id,
                    "url_sample": new_url,
                    "has_avatar": contact["has_avatar"]
                })
                logger.info(f"  → ID: {contact_id}")

                driver.back()
                driver.wait_for_element("button.cell", timeout=10)
                time.sleep(random.uniform(1.0, 2.5))

            except Exception as e:
                logger.error(f"Ошибка с '{name}': {e}")
                try:
                    driver.back()
                    driver.wait_for_element("button.cell", timeout=8)
                except:
                    pass
                continue

        # Объединяем старые + новые и сохраняем
        final_results = existing_results + new_results
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)

        logger.info(f"=== Готово! Всего в базе: {len(final_results)} контактов ===")
        logger.info(f"Файл сохранён: {output_file}")

        return {
            "status": "успешно",
            "новых_обработано": len(new_results),
            "всего_в_базе": len(final_results),
            "файл": output_file
        }


def send_message_to_contact(
    contact_name: str,
    message: str,
    json_file: str = "max_contacts_with_ids.json",
    profile_dir: str = "/home/akozh/PycharmProjects/Maxer/browser_profile"
):
    logger.info(f"=== Отправка сообщения контакту: {contact_name} ===")

    # Загружаем базу контактов
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            contacts = json.load(f)
    except FileNotFoundError:
        return {"status": "ошибка", "причина": "Файл базы не найден"}

    contact = next(
        (c for c in contacts if c["name"].lower() == contact_name.lower() or
         "избранное" in c["name"].lower()),
        None
    )
    if not contact or not contact.get("id"):
        return {"status": "ошибка", "причина": f"Контакт '{contact_name}' не найден"}

    contact_id = contact["id"]
    chat_url = f"https://web.max.ru/{contact_id}"   # ← правильная ссылка

    with Driver(uc=True, headless=False, user_data_dir=profile_dir) as driver:
        try:
            driver.get(chat_url)
            time.sleep(2.5)

            # Поиск поля ввода
            input_element = driver.wait_for_element(
                "div.contenteditable.svelte-1k31az8",
                timeout=10
            )

            input_element.click()
            time.sleep(0.7)

            # Вставка текста (Lexical)
            driver.execute_script("""
                const editor = arguments[0];
                const text = arguments[1];
                editor.focus();
                const selection = window.getSelection();
                selection.selectAllChildren(editor);
                selection.deleteFromDocument();
                document.execCommand('insertText', false, text);
                editor.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
            """, input_element, message)

            time.sleep(0.6)

            from selenium.webdriver.common.keys import Keys
            input_element.send_keys(Keys.ENTER)

            time.sleep(1.5)
            logger.info("✅ Сообщение отправлено")

            return {
                "status": "успешно",
                "контакт": contact_name,
                "id": contact_id
            }

        except Exception as e:
            logger.error(f"Ошибка при отправке: {e}")
            return {"status": "ошибка", "причина": str(e)}

    # Браузер автоматически закроется здесь (после выхода из with)


def get_last_messages(chat_name: str, count: int = 5) -> list[dict]:
    """
    Возвращает последние N сообщений из чата.
    """
    logger.info(f"Читаем последние {count} сообщений из чата: {chat_name}")

    # Находим контакт и переходим в чат (используем существующую логику)
    try:
        with open("max_contacts_with_ids.json", "r", encoding="utf-8") as f:
            contacts = json.load(f)
    except:
        return []

    contact = next((c for c in contacts if c["name"].lower() == chat_name.lower()), None)
    if not contact or not contact.get("id"):
        logger.error(f"Контакт {chat_name} не найден")
        return []

    chat_url = f"https://web.max.ru/{contact['id']}"

    with Driver(uc=True, headless=False, user_data_dir="/home/akozh/PycharmProjects/Maxer/browser_profile") as driver:
        driver.get(chat_url)
        time.sleep(3)

        # Ищем все сообщения
        bubbles = driver.find_elements("css selector", "div[data-bubbles-variant]")

        if not bubbles:
            logger.warning("Сообщения не найдены")
            return []

        # Берём последние N сообщений (они обычно в конце)
        last_bubbles = bubbles[-count:] if len(bubbles) > count else bubbles

        messages = []
        for bubble in last_bubbles:
            try:
                variant = bubble.get_attribute("data-bubbles-variant")
                is_outgoing = variant == "outgoing"

                # Текст сообщения
                text_el = bubble.find_element("css selector", "span.text.svelte-1htnb3l")
                text = text_el.text.strip()

                # Время
                try:
                    time_el = bubble.find_element("css selector", "span.meta .text.svelte-13lobfv")
                    msg_time = time_el.text.strip()
                except:
                    msg_time = ""

                sender = "Ты" if is_outgoing else chat_name

                messages.append({
                    "sender": sender,
                    "text": text,
                    "time": msg_time,
                    "is_outgoing": is_outgoing
                })
            except Exception as e:
                continue

        logger.info(f"Получено {len(messages)} сообщений")
        return messages


if __name__ == "__main__":
    print("🚀 === ТЕСТ МАКСЕР ===\n")

    # === ТЕСТ 1: Отправка сообщения ===
    print("[1] Отправка сообщения в Избранное...")
    send_result = send_message_to_contact(
        contact_name="Избранное",
        message="Тестовая отправка из Максер"
    )
    print("Результат отправки:", send_result)

    # === ТЕСТ 2: Чтение последних сообщений ===
    print("\n[2] Чтение последних 5 сообщений из Избранного...")
    messages = get_last_messages("Избранное", count=5)

    print(f"Получено сообщений: {len(messages)}")
    for i, msg in enumerate(messages, 1):
        direction = "→" if msg["is_outgoing"] else "←"
        print(f"{i}. {direction} [{msg['time']}] {msg['sender']}: {msg['text'][:80]}...")

    print("\n✅ Тест завершён")