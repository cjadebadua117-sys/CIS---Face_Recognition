import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from .models import AttendanceRecord, Schedule


class AttendanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.schedule_id = self.scope['url_route']['kwargs']['schedule_id']
        self.room_group_name = f'attendance_schedule_{self.schedule_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')

        if message_type == 'attendance_update':
            await self.handle_attendance_update(text_data_json)

    async def handle_attendance_update(self, data):
        # Broadcast attendance update to all clients in the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'attendance_update',
                'user': data['user'],
                'status': data['status'],
                'timestamp': data['timestamp'],
                'confidence': data.get('confidence'),
            }
        )

    # Receive message from room group
    async def attendance_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'attendance_update',
            'user': event['user'],
            'status': event['status'],
            'timestamp': event['timestamp'],
            'confidence': event.get('confidence'),
        }))