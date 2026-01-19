from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, List, Literal, Any
from datetime import datetime
from bson import ObjectId
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Any
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ])
        ],
        serialization=core_schema.plain_serializer_function_ser_schema(
            lambda x: str(x)
        ))

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string"}

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class Table(BaseModel):
    tableName: str
    capacity: int
    status: str  # Changed from Literal to str to accept any status like "BOOKED"
    floorId: str

    model_config = ConfigDict(
        populate_by_name=True,
        extra='allow'  # Allow extra fields from MongoDB
    )


class Guest(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    phone: Optional[str] = None
    partySize: Optional[int] = None
    status: Literal["assigned", "unassigned", "completed", "arrived", "waiting", "seated", "finished"] = "unassigned"
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    stayFrom: Optional[datetime] = None
    stayTo: Optional[datetime] = None
    isFirstTime: bool = True
    dietaryPreferences: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    arrivalTime: Optional[str] = None
    estimatedWait: Optional[int] = None
    table: Optional[Table] = None

    @field_serializer('id')
    def serialize_id(self, value: Optional[PyObjectId], _info):
        return str(value) if value else None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra='allow'
    )


class DiningHistory(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    guestId: str
    guestName: str
    tableName: str
    partySize: int
    foodOrdered: List[str] = Field(default_factory=list)
    visitDate: datetime = Field(default_factory=datetime.utcnow)
    preferences: List[str] = Field(default_factory=list)

    @field_serializer('id')
    def serialize_id(self, value: Optional[PyObjectId], _info):
        return str(value) if value else None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra='allow'
    )


# 🟢 NEW: Floor Plan Models

class PixelCoordinates(BaseModel):
    """Pixel coordinates in the image"""
    x: int
    y: int
    width: int
    height: int


class CenterPoint(BaseModel):
    """Center point in real-world coordinates"""
    x: float
    y: float


class RealWorldCoordinates(BaseModel):
    """Real-world coordinates with measurements"""
    x: float
    y: float
    width: float
    height: float
    unit: str = "meters"
    centerPoint: CenterPoint
    area: Optional[float] = None


class DetectedTable(BaseModel):
    """Single detected table from floor plan"""
    tableId: str
    detectionMethod: Literal["yolo", "shape"] = "yolo"
    detectedClass: Optional[str] = None
    pixelCoordinates: PixelCoordinates
    realWorldCoordinates: RealWorldCoordinates
    confidence: float = Field(ge=0.0, le=1.0)


class RoomDimensions(BaseModel):
    """Room dimensions for scaling"""
    length: float = Field(gt=0, description="Room length")
    width: float = Field(gt=0, description="Room width")
    unit: str = Field(default="meters", description="Measurement unit")


class FloorPlanAnalysis(BaseModel):
    """Floor plan analysis result"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    floorPlanUrl: str
    analysisStatus: Literal["processing", "completed", "failed"] = "processing"
    detectedTables: List[DetectedTable] = Field(default_factory=list)
    annotatedFloorPlanUrl: Optional[str] = None
    roomDimensions: RoomDimensions
    tableCount: Optional[int] = 0
    error: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    @field_serializer('id')
    def serialize_id(self, value: Optional[PyObjectId], _info):
        return str(value) if value else None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra='allow'
    )


# 🔴 DEPRECATED: Old video analysis models (keeping for backward compatibility)

class DetectedObject(BaseModel):
    """Deprecated: Use DetectedTable instead"""
    type: str
    coordinates: dict
    confidence: float = 0.75


class VideoAnalysis(BaseModel):
    """Deprecated: Use FloorPlanAnalysis instead"""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    videoUrl: str
    analysisStatus: Literal["processing", "completed", "failed"] = "processing"
    detectedObjects: List[DetectedObject] = Field(default_factory=list)
    staticImageUrl: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)

    @field_serializer('id')
    def serialize_id(self, value: Optional[PyObjectId], _info):
        return str(value) if value else None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra='allow'
    )