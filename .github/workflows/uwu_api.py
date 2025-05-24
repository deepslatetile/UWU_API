import sqlite3
import string
from flask import Flask, request, jsonify, make_response
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import datetime as dt
import random
from ftplib import FTP
from flask_cors import CORS
import os
import subprocess
import re
import time
import threading
import requests
import pandas as pd

import sys
import requests
from io import StringIO


class WebhookIO(StringIO):
    def __init__(self, original_stream, webhook_url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_stream = original_stream
        self.webhook_url = webhook_url
        self.buffer = ""

    def write(self, s):
        # Перенаправляем в оригинальный поток
        self.original_stream.write(s)

        # Добавляем в буфер
        self.buffer += s

        # Если есть перевод строки, отправляем сообщение
        if '\n' in self.buffer:
            self.flush()

    def flush(self):
        if self.buffer.strip():
            # Форматируем и отправляем через вебхук
            message = f"```{self.buffer.strip()}```"[:1990]
            data = {
                'content': message,
                'avatar_url': "#",
                'username': "UWU API"
            }
            response = requests.post(self.webhook_url, json=data)
            if response.status_code != 204:
                self.original_stream.write(f"Webhook error: {response.text}\n")

        # Очищаем буфер
        self.buffer = ""
        super().flush()


def setup_webhook_logging(webhook_url):
    # Перенаправляем stdout и stderr
    sys.stdout = WebhookIO(sys.stdout, webhook_url)
    sys.stderr = WebhookIO(sys.stderr, webhook_url)


# Пример использования
WEBHOOK_URL = "#"
setup_webhook_logging(WEBHOOK_URL)




app = Flask(__name__)

cors = CORS(
    app,
    resources={
        r'/*': {
            'origins': '*'
        }
    }
)


#
conn = sqlite3.connect('memories.db')
cursor = conn.cursor()
cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT NOT NULL,
                caption TEXT,
                date TEXT,
                user_id TEXT
            )
            ''')


def generate_booking_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def generate_boarding_pass(flight_number: str, booking_id: str, roblox_nickname: str,
                           roblox_displayname: str, flight_class: str, seat: str):
    # Get flight details
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute("SELECT departure, arrival, datetime FROM flights WHERE flight_number = ?", (flight_number,))
    flight = c.fetchone()
    conn.close()

    if not flight:
        return None

    departure, arrival, datetime_str = flight
    date_part, time_part = datetime_str.split(' ')

    # Create boarding pass image
    bg_color = (5, 15, 45)  # #050F2D
    text_color = (251, 233, 227)  # #FBE9E3
    accent_color = (100, 100, 150)

    # Image dimensions
    width = 800
    height = 400

    image = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    try:
        font_path = "arialbd.ttf"
        title_font = ImageFont.truetype(font_path, 24)
        header_font = ImageFont.truetype(font_path, 18)
        text_font = ImageFont.truetype(font_path, 16)
        small_font = ImageFont.truetype(font_path, 14)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Draw title
    draw.text((20, 20), "UWU ALLIANCE BOARDING PASS", fill=text_color, font=title_font)

    # Draw flight info
    draw.text((20, 70), f"Flight: {flight_number}", fill=text_color, font=header_font)
    draw.text((200, 70), f"Date: {date_part}", fill=text_color, font=header_font)
    draw.text((400, 70), f"Time: {time_part}", fill=text_color, font=header_font)

    # Draw passenger info
    draw.text((20, 120), f"Passenger: {roblox_displayname} (@{roblox_nickname})", fill=text_color, font=text_font)
    draw.text((20, 150), f"Class: {flight_class}", fill=text_color, font=text_font)
    draw.text((20, 180), f"Seat: {seat}", fill=text_color, font=text_font)

    # Draw route
    draw.text((400, 120), f"Route: {departure} → {arrival}", fill=text_color, font=text_font)

    # Draw booking ID
    draw.text((20, 350), f"Booking ID: {booking_id}", fill=accent_color, font=small_font)

    # Draw barcode placeholder
    draw.rectangle([(500, 250), (750, 350)], outline=accent_color, width=2)
    draw.text((600, 290), "BOARDING PASS", fill=accent_color, font=small_font)

    # Save image to buffer and convert to base64
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

    return img_base64


def norm_flight_number(fn):
    fn = fn.replace(' ', '').upper()
    return f"{fn[:2]} {fn[2:]}"


def printy(s):
    print(s)
    s = f"```{s}"[:1990] + '```'
    data = {
        'content': s,
        'avatar_url': "#",
        'username': "UWU API"
    }
    response = requests.post("#", json=data)
    if response.status_code != 204:
        print(f"{response.text}")


@app.route('/bookings/<string:flight_number>', methods=['GET'])
def get_bookings(flight_number):
    flight_number = norm_flight_number(flight_number)

    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bookings WHERE flight_number = ? ORDER BY created_at", (flight_number,))
    bookings = c.fetchall()
    conn.close()

    if not bookings:
        return jsonify(f"No bookings found for flight {flight_number}"), 400

    response = {}
    for booking in bookings:
        booking_id, _, roblox_nickname, roblox_displayname, req_class, ass_class, seat, discord_id, _ = booking
        response[booking_id] = {
            "roblox_nickname": roblox_nickname,
            "roblox_displayname": roblox_displayname,
            "class": ass_class or req_class,
            "seat": seat or 'Not assigned',
            "discord_id": discord_id or None
        }

    return jsonify(response), 200


@app.route('/bookings/new_booking/', methods=['POST'])
def new_booking():
    data = request.get_json()
    try:
        flight_number = data["flight_number"].replace(' ', '')
        flight_number = flight_number[:2] + ' ' + flight_number[2:]
        roblox_nickname = data["roblox_nickname"]
        roblox_displayname = data["roblox_displayname"]
        discord_id = data["discord_id"]
        flight_class = data["flight_class"]
        seat = data["seat"]
    except Exception:
        return jsonify("Something went wrong. Check body of your request"), 400

    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM flights WHERE flight_number = ?", (flight_number,))
    flight_exists = c.fetchone()
    conn.close()

    if not flight_exists:
        return jsonify("Flight not found"), 400

    # Generate booking ID
    booking_id = generate_booking_id()
    created_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save booking to database (including Discord user ID)
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (booking_id, flight_number, roblox_nickname, roblox_displayname,
                   flight_class or 'Economy', flight_class, seat, discord_id, created_at))
        conn.commit()
        return jsonify(booking_id), 200
    except sqlite3.IntegrityError:
        return jsonify("Error while creating booking, try again"), 500
    finally:
        conn.close()


@app.route('/bookings/boardpass/', methods=['POST'])
def boardpass():
    data = request.get_json()
    try:
        booking_id = data["booking_id"]
        new_class = data["assigned_class"]
        new_seat = data["seat"]
    except KeyError:
        return jsonify("Missing required fields"), 400

    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("SELECT flight_number, roblox_nickname, roblox_displayname, requested_class, assigned_class, seat FROM bookings WHERE booking_id = ?", (booking_id,))
    booking = c.fetchone()

    if not booking:
        conn.close()
        return jsonify("Booking not found"), 400

    flight_number, roblox_nickname, roblox_displayname, requested_class, assigned_class, seat = booking
    flight_class = new_class if new_class is not None else (assigned_class or requested_class)
    seat = new_seat if new_seat is not None else seat

    # Update booking in database
    c.execute("UPDATE bookings SET assigned_class = ?, seat = ? WHERE booking_id = ?",
              (flight_class, seat, booking_id))
    conn.commit()
    conn.close()

    # Generate boarding pass
    img_base64 = generate_boarding_pass(
        flight_number, booking_id, roblox_nickname,
        roblox_displayname, flight_class, seat
    )

    if not img_base64:
        return jsonify("Error generating boarding pass"), 500

    return jsonify(img_base64), 200


@app.route('/sql/boardpass/<string:flight_number>', methods=['GET'])
def sql_boardpass(flight_number):
    # generate_boarding_pass()
    flight_number = norm_flight_number(flight_number)
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute("SELECT departure, arrival, datetime FROM flights WHERE flight_number = ?", (flight_number,))
    flight = c.fetchone()
    conn.close()

    if not flight:
        return jsonify("None"), 400

    printy(flight)
    return jsonify(flight), 200


@app.route('/sql/book/s1/<string:flight_number>', methods=['GET'])
def sql_book_s1(flight_number):
    flight_number = norm_flight_number(flight_number)
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM flights WHERE flight_number = ?", (flight_number,))
    flight_exists = c.fetchone()
    conn.close()
    if not flight_exists:
        return jsonify("None"), 400
    return jsonify("Flight exists"), 200


@app.route('/sql/book/s2/', methods=['POST'])
def sql_book_s2():
    data = request.get_json()
    try:
        flight_number = data["flight_number"]
        flight_number = norm_flight_number(flight_number)
        roblox_nickname = data["roblox_nickname"]
        roblox_displayname = data["roblox_displayname"]
        flight_class = data["flight_class"]
        discord_user_id = data["discord_user_id"]
    except KeyError:
        return jsonify("Missing required fields"), 400

    booking_id = generate_booking_id()
    created_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (booking_id, flight_number, roblox_nickname, roblox_displayname,
                   flight_class, None, None, discord_user_id, created_at))
        conn.commit()
        return jsonify(str(booking_id)), 200
    except sqlite3.IntegrityError:
        return jsonify("Error"), 500
    finally:
        conn.close()


@app.route('/sql/boardpass/s1/<string:booking_id>', methods=['GET'])
def sql_boardpass_s1(booking_id):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("SELECT flight_number, roblox_nickname, roblox_displayname, discord_user_id FROM bookings WHERE booking_id = ?", (booking_id,))
    booking = c.fetchone()
    if not booking:
        return jsonify("Booking not found"), 400
    return jsonify(booking), 200


@app.route('/sql/boardpass/s2/', methods=['POST'])
def sql_boardpass_s2():
    data = request.get_json()
    try:
        flight_class = data["flight_class"]
        seat = data["seat"]
        booking_id = data["booking_id"]
    except KeyError:
        return jsonify("Missing required fields"), 400

    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("UPDATE bookings SET assigned_class = ?, seat = ? WHERE booking_id = ?",
              (flight_class, seat, booking_id))
    conn.commit()
    conn.close()


@app.route('/sql/delbook/<string:booking_id>', methods=['GET'])
def sql_delbook(booking_id):
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))

    if c.rowcount == 0:
        return jsonify("Booking not found"), 400
    else:
        conn.commit()
        return jsonify(f"Booking {booking_id} deleted"), 200


@app.route('/sql/booklistadmin/', methods=['GET'])
def sql_booklistadmin():
    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bookings ORDER BY created_at")
    bookings = c.fetchall()
    conn.close()

    if not bookings:
        return jsonify("No bookings found"), 400

    response = ""
    for booking in bookings:
        booking_id, flight_number, roblox_nickname, roblox_displayname, req_class, ass_class, seat, _, _ = booking
        response += f"```{booking_id}; {flight_number}; {roblox_displayname}; (@{roblox_nickname}); {ass_class or req_class}; {seat or 'Not assigned'}```\n"

    return jsonify(response), 200


@app.route('/sql/newflight/', methods=['POST'])
def sql_newflight():
    data = request.get_json()
    if not data:
        return jsonify("No JSON data received"), 400

    try:
        flight_number = data.get("flight_number")
        departure = data.get("departure")
        arrival = data.get("arrival")
        datentime = data.get("datentime")
        status = data.get("status")
        event_id = data.get("event_id")

        if None in [flight_number, departure, arrival, datentime, status, event_id]:
            return jsonify("Missing required fields"), 400

        flight_number = norm_flight_number(flight_number)

        conn = sqlite3.connect('flights.db')
        c = conn.cursor()
        c.execute("INSERT INTO flights VALUES (?, ?, ?, ?, ?, ?)",
                  (flight_number, departure, arrival, datentime, status, str(event_id)))
        conn.commit()
        conn.close()
        return jsonify('Flight created'), 200

    except Exception as e:
        printy(f"Error in sql_newflight: {str(e)}")
        return jsonify(f"Error occurred: {str(e)}"), 500


@app.route('/sql/editflight/', methods=['POST'])
def sql_editflight():
    data = request.get_json()
    printy(data)
    try:
        flight_number = data["flight_number"]
        param = data["param"]
        new_info = data["new_info"]
    except KeyError:
        return jsonify("Missing required fields"), 400

    flight_number = norm_flight_number(flight_number)

    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM flights WHERE flight_number = ?", (flight_number,))
        flight = c.fetchone()
        if not flight:
            conn.close()
            return jsonify("Flight not found"), 400

        c.execute(f"UPDATE flights SET {param} = ? WHERE flight_number = ?", (new_info, flight_number))
        conn.commit()

        flight_data = {
            "flight_number": flight[0],
            "departure": flight[1],
            "arrival": flight[2],
            "datetime": flight[3],
            "status": flight[4],
            "event_id": flight[5]
        }

        conn.close()
        return jsonify(flight_data), 200

    except Exception as e:
        printy(e)
        conn.close()
        return jsonify(f"Something went wrong: {str(e)}"), 500


@app.route('/sql/editflight/event_upd/', methods=['POST'])
def sql_editflight_event():
    data = request.get_json()
    try:
        flight_number = data["flight_number"]
        event_id = data["event_id"]
    except KeyError:
        return jsonify("Missing required fields"), 400

    flight_number = norm_flight_number(flight_number)

    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    try:
        c.execute("UPDATE flights SET event_id = ? WHERE flight_number = ?", (str(event_id), flight_number))
    except Exception as e:
        printy(e)
        return jsonify("Something went wrong"), 500

    conn.commit()
    conn.close()
    return jsonify("Updated"), 200


@app.route('/sql/delflight/<string:flight_number>', methods=['GET'])
def sql_delflight(flight_number):
    flight_number = norm_flight_number(flight_number)
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()

    try:
        c.execute("SELECT event_id FROM flights WHERE flight_number = ?", (flight_number,))
        event_id = c.fetchone()[0]
        c.execute("DELETE FROM flights WHERE flight_number = ?", (flight_number,))

        if c.rowcount == 0:
            return jsonify("Flight not found"), 400
        else:
            conn.commit()
            return jsonify(f"{event_id}"), 200
    except Exception as e:
        printy(f"Error deleting flight: {e}")
        return jsonify(f"Error occured\n{e}"), 500
    finally:
        conn.close()


@app.route('/sql/schedule/', methods=['GET'])
def sql_schedule():
    conn = sqlite3.connect('flights.db')
    c = conn.cursor()
    c.execute("SELECT * FROM flights ORDER BY datetime")  # Получаем расписание рейсов
    flights = c.fetchall()
    conn.close()
    if not flights:
        printy("Flight schedule is empty")
        return jsonify("Flight schedule is empty"), 200

    return jsonify(flights), 200


@app.route('/sql/archive/<string:flight_number>', methods=['GET'])
def sql_archive(flight_number):
    flight_number = norm_flight_number(flight_number)

    conn = sqlite3.connect('bookings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM bookings WHERE flight_number = ?", (flight_number,))
    bookings = c.fetchall()

    if not bookings:
        return jsonify(f"No bookings found for flight {flight_number}."), 400

    # Create DataFrame
    columns = [
        'booking_id', 'flight_number', 'roblox_nickname', 'roblox_displayname',
        'requested_class', 'assigned_class', 'seat', 'discord_user_id', 'created_at'
    ]
    df = pd.DataFrame(bookings, columns=columns)

    # Excel file handling
    excel_file = "archived_bookings.xlsx"

    # Check if file exists and is valid
    file_exists = os.path.exists(excel_file) and os.path.getsize(excel_file) > 0

    if file_exists:
        try:
            # Read existing data with explicit engine
            existing_df = pd.read_excel(excel_file, engine='openpyxl')
            combined_df = pd.concat([existing_df, df], ignore_index=True)
        except Exception as e:
            # If reading fails, create new file
            printy(f"Error reading existing file, creating new: {e}")
            combined_df = df
    else:
        combined_df = df

    # Save to Excel with explicit engine
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        combined_df.to_excel(writer, index=False)

    # Delete from database
    c.execute("DELETE FROM bookings WHERE flight_number = ?", (flight_number,))
    conn.commit()

    return jsonify(
        f"Successfully archived {len(bookings)} bookings for flight {flight_number}."), 200


@app.route('/sql/memory/', methods=['POST'])
def sql_memory():
    data = request.get_json()
    try:
        image = data["image"]
        caption = data["caption"]
        memdate = data["memdate"]
        user_id = data["user_id"]
    except KeyError:
        return jsonify("Missing required fields"), 400

    try:
        conn = sqlite3.connect('memories.db')
        cursor = conn.cursor()
        cursor.execute('''
                    INSERT INTO images (image, caption, date, user_id)
                    VALUES (?, ?, ?, ?)
                    ''', (image, caption, memdate, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        printy(e)
        return jsonify(f"Error {e}"), 500
    return jsonify("Saved"), 200


@app.route('/sql/notify/s1/<string:flight_number>', methods=['GET'])
def sql_notify_s1(flight_number):
    flight_number = norm_flight_number(flight_number)

    try:
        conn = sqlite3.connect('flights.db')
        c = conn.cursor()
        c.execute("SELECT departure, arrival FROM flights WHERE flight_number = ?", (flight_number,))
        flight_data = c.fetchone()
        conn.close()
    except Exception as e:
        printy(e)
        return jsonify("Something went wrong"), 500

    return jsonify(flight_data), 200


@app.route('/sql/notify/s2/<string:flight_number>', methods=['GET'])
def sql_notify_s2(flight_number):
    flight_number = norm_flight_number(flight_number)

    try:
        conn = sqlite3.connect('bookings.db')
        c = conn.cursor()
        c.execute("SELECT discord_user_id FROM bookings WHERE flight_number = ?", (flight_number,))
        users_with_booking = c.fetchall()
        conn.close()
    except Exception as e:
        printy(e)
        return jsonify("Something went wrong"), 500

    return jsonify(users_with_booking), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3525)
