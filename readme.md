# Restaurant Seat Management API

AI-powered restaurant table management system with video analysis.

## Features

1. **Guest Management** - CRUD operations for guests
2. **AI Suggestions** - Claude AI suggests tables, party size, and food preferences based on history
3. **Video Analysis** - Upload restaurant video to detect tables, doors, pillars

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create `.env` file:
```bash
# MongoDB (already configured)
MONGODB_URL=mongodb+srv://hello_prisma:hello_prisma@cluster0.bomlehy.mongodb.net/resturant_table?appName=Cluster0
DATABASE_NAME=resturant_table

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=restaurant-videos

# Claude API
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 3. Get API Keys

**Claude API Key:**
- Visit: https://console.anthropic.com/
- Sign up and get API key
- Cost: ~$3 per million tokens (very affordable)

**AWS S3:**
- Create AWS account: https://aws.amazon.com/
- Create S3 bucket named `restaurant-videos`
- Get access keys from IAM console
- Set bucket to public or use presigned URLs

### 4. Run Server
```bash
python main.py
```

Server will start at: http://localhost:8000

## API Endpoints

### Guest Management

**GET /api/guests/** - Get all guests
```json
Response: {
  "statusCode": 200,
  "success": true,
  "data": {
    "assignedCount": 1,
    "unassignedCount": 12,
    "guests": [...]
  }
}
```

**POST /api/guests/** - Create new guest
```json
Request Body: {
  "name": "John Doe",
  "phone": "1234567890",
  "partySize": 4,
  "dietaryPreferences": ["VEGAN"]
}
```

**GET /api/guests/suggestions/{guest_id}** - Get AI suggestions
```json
Response: {
  "suggestedTable": "T-5",
  "suggestedPartySize": 4,
  "suggestedFoods": ["Vegan Pasta", "Salad"],
  "reasoning": "Based on 3 previous visits..."
}
```

### Video Analysis

**POST /api/video/upload** - Upload restaurant video
```bash
curl -X POST -F "video=@restaurant.mp4" http://localhost:8000/api/video/upload
```

**GET /api/video/analysis/{analysis_id}** - Get analysis result
```json
Response: {
  "detectedObjects": [
    {
      "type": "table",
      "coordinates": {"x": 100, "y": 200, "width": 50, "height": 50},
      "confidence": 0.85
    }
  ],
  "staticImageUrl": "https://..."
}
```

## Project Structure
```
restaurant-management/
├── main.py              # FastAPI app
├── config.py            # Settings
├── database.py          # MongoDB connection
├── models.py            # Data models
├── routes/
│   ├── guests.py        # Guest routes
│   └── video.py         # Video routes
├── services/
│   ├── ai_service.py    # Claude AI
│   ├── video_service.py # Video processing
│   └── s3_service.py    # AWS S3
└── utils.py             # Helpers
```

## Database Collections

**guests** - Guest information
**dining_history** - Past visits and preferences
**video_analysis** - Video processing results

## Cost Estimation

- **Claude API**: ~$0.003 per suggestion (very cheap)
- **AWS S3**: $0.023 per GB storage + $0.09 per GB transfer
- **Total**: ~$10-20/month for small restaurant

## Testing

```bash
# Test API
curl http://localhost:8000/

# Test guest creation
curl -X POST http://localhost:8000/api/guests/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","phone":"1234567890","partySize":2}'
```

## Notes

- Video analysis uses simple contour detection (upgrade to YOLO for better accuracy)
- Claude AI provides contextual suggestions based on dining history
- S3 stores videos and static images
- MongoDB stores all data persistently