#!/usr/bin/env python3

import aiohttp
import asyncio
import base64
import datetime
import json
import urllib.parse

from beaupy import confirm, select
from beaupy.spinners import Spinner
from rich.console import Console

console = Console()

base_url = "https://ga.healthinspections.us/stateofgeorgia/API/index.cfm"
filters_url = f"{base_url}/filters"
search_url = "/search/"
report_url = "/inspectionsData/"


async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.json()


async def url_encode(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return response.url.query_string


async def prompt_user(message):
    user_input = input(message)
    return user_input


async def get_keyword():
    while True:
        keyword = input(
            "Enter the name or partial name of the establishment (Optional): ")
        try:
            return keyword
        except ValueError:
            print("Invalid input. Please try again.")


async def get_valid_date():
    while True:
        chosen_date = input("Enter the start date (MM/DD/YYYY): ")
        user_choice = f"{chosen_date[:2]}/{chosen_date[2:4]}/{chosen_date[4:]}"
        try:
            date_obj = datetime.datetime.strptime(user_choice, "%m/%d/%Y")
            return date_obj.strftime("%m/%d/%Y")
        except ValueError:
            print("Invalid date format. Please try again.")


async def get_score_range():
    while True:
        try:
            low_score = int(input("Enter the lowest score range (0-100): "))
            high_score = int(input("Enter the highest score range (0-100): "))
            if 0 <= low_score <= 100 and 0 <= high_score <= 100:
                if low_score <= high_score:
                    return low_score, high_score
                else:
                    print(
                        "Invalid score range. The highest score cannot be lower than the lowest score.")
            else:
                print("Invalid score range. Please enter values between 0 and 100.")
        except ValueError:
            print("Invalid input. Please enter numeric values.")


def encode_string(string):
    encoded_string = base64.b64encode(string.encode('utf-8')).decode()
    return encoded_string


def encode_int(integer):
    encoded_int = base64.b64encode(str(integer).encode()).decode()
    return encoded_int


def encode_url(value):
    return urllib.parse.quote(value)


async def get_violations(session, id):
    url = base_url + report_url + id
    async with session.get(url) as response:
        return await response.json()


async def fetch_reports(keyword, city, county, permit, score_range, start_date, formatted_date):
    spinner_animation = ['🏥🚑    🍽️ ', '🏥 🚑   \
                        🍽️ ', '🏥  🚑  🍽️ ', '🏥   🚑 🍽️ ', '🏥    🚑🍽️ '][::-1]

    spinner = Spinner(spinner_animation,
                      "Fetching health inspection reports...")
    spinner.start()

    low_score = score_range[0]
    high_score = score_range[1]

    advanced_payload = {
        "city": encode_string(city),
        "county": encode_string(county),
        "scoreFrom": encode_int(low_score),
        "scoreTo": encode_int(high_score),
        "permitType": encode_string(permit),
        "from": encode_string(start_date),
        "to": encode_string(formatted_date),
        "keyword": encode_string(keyword)
    }

    async with aiohttp.ClientSession(trust_env=True) as session:
        tasks = []
        for i in range(0, 500):
            url = base_url + search_url + \
                encode_url(json.dumps(advanced_payload)) + "/" + str(i)
            tasks.append(fetch(session, url))
        responses = await asyncio.gather(*tasks)

        array = []
        for res in responses:
            for key in res:
                name = key["name"]
                id = key["id"]
                address = key["mapAddress"].replace("\n", "").replace("\r", "")
                score = int(key["columns"]["4"].split(":")[1].strip())
                date = key["columns"]["5"].split(":")[1].strip()

                violations = await get_violations(session, id)
                if violations:
                    array.append({
                        "name": name,
                        "id": int(str(base64.b64decode(id), "utf-8")),
                        "score": score,
                        "address": address,
                        "date": date,
                        "violations": violations[0]["violations"]
                    })

        if array:
            array.sort(key=lambda x: x["score"])
            formatted_output = json.dumps(array, indent=2)
            print(formatted_output)
        else:
            print("No inspection reports found that meet the criteria")

    spinner.stop()


async def main():
    try:
        keyword = await get_keyword()
        data = await fetch_data(filters_url)
        cities = data[0]["values"]
        counties = data[1]["values"]
        permit_types = data[3]["values"]

        city = select(cities, cursor="➜", cursor_style="pink1",
                      pagination=True, page_size=15)
        county = select(counties, cursor="➜", cursor_style="pink1",
                        pagination=True, page_size=15)
        permit = select(permit_types, cursor="➜", cursor_style="pink1")

        today = datetime.date.today()
        formatted_date = today.strftime("%m/%d/%Y")

        start_date = await get_valid_date()

        score_range = await get_score_range()

        confirm_message = confirm(
            f"\nAre these the correct values?\nEstablishment Name or Partial Name: {keyword}\nCity: {city}\nCounty: {county}\nPermit: {permit}\nLowest Score: {score_range[0]}\nHighest Score: {score_range[1]}\nStart Date: {start_date}\nEnd Date: {formatted_date}"
        )

        if confirm_message:
            await fetch_reports(keyword, city, county, permit, score_range, start_date, formatted_date)
        elif confirm_message == False:
            exit_message = "Do you want to exit the program? (y/n): "
            exit_input = input(exit_message)
            if exit_input.lower() == "y":
                exit("Goodbye")
            elif exit_input.lower() == "n":
                await main()
            else:
                print("Invalid input. Please try again.")
                await main()
        else:
            await main()
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
