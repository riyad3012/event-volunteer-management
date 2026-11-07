
import requests

url = "http://127.0.0.1:5000/register"

data = {
    "name": "Test Volunteer",
    "email": "testvolunteer@gmail.com",
    "password": "Test@12345",
    "phone": "9876543210",
    "role": "volunteer"
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Response:", response.json())
