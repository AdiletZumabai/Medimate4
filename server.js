const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const twilio = require('twilio');
const nodemailer = require('nodemailer');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(bodyParser.json());

const twilioClient = twilio(process.env.TWILIO_SID, process.env.TWILIO_AUTH_TOKEN);

// Email конфигурация
const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS
    }
});

// Установка напоминания
app.post('/set-reminder', (req, res) => {
    const { medicationName, reminderTime, frequency, phone, email } = req.body;

    console.log(`Reminder set for ${medicationName} at ${reminderTime} for ${frequency}`);

    const [hour, minute] = reminderTime.split(":");
    const now = new Date();
    const reminderDate = new Date();
    reminderDate.setHours(hour, minute, 0, 0);

    if (reminderDate < now) {
        reminderDate.setDate(now.getDate() + 1);
    }

    const timeDiff = reminderDate.getTime() - now.getTime();

    setTimeout(() => {
        if (phone) {
            sendSMS(phone, medicationName);
        }
        if (email) {
            sendEmail(email, medicationName);
        }
    }, timeDiff);

    res.json({ message: "Reminder successfully set!" });
});

// Функция отправки SMS через Twilio
function sendSMS(phone, medicationName) {
    twilioClient.messages.create({
        body: `Reminder: It's time to take your medication - ${medicationName}!`,
        from: process.env.TWILIO_PHONE,
        to: phone
    }).then(() => console.log(`SMS sent to ${phone}`))
    .catch(err => console.error("Twilio Error:", err));
}

// Функция отправки Email через Nodemailer
function sendEmail(email, medicationName) {
    const mailOptions = {
        from: process.env.EMAIL_USER,
        to: email,
        subject: "MediMate Medication Reminder",
        text: `Reminder: It's time to take your medication - ${medicationName}!`
    };

    transporter.sendMail(mailOptions, (error, info) => {
        if (error) {
            console.error("Email Error:", error);
        } else {
            console.log(`Email sent to ${email}: ${info.response}`);
        }
    });
}

app.listen(5000, () => {
    console.log('Server running on port 5000');
});
