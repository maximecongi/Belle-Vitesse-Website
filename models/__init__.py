from models.db import _utcnow, db, generate_inspection_number
from models.user import User
from models.project import Contact, Production, Project
from models.mixins import SignedDocumentMixin, TokenMixin
from models.inspection import (
    BaseInspectionVehicle,
    CheckinSignedDocument,
    CheckinToken,
    CheckinVehicle,
    CheckoutSignedDocument,
    CheckoutToken,
    CheckoutVehicle,
    InspectionCheckpoint,
    VehicleCheckpointConfig,
)
from models.checkpoint import CheckpointDefinition
from models.waiver import (
    CglWaiver,
    PilotWaiver,
    RiskAssessmentWaiver,
    SafetyRulesWaiver,
    Waiver,
    WaiverSignedDocument,
    WaiverToken,
)
from models.catalog import (
    SyncRecordMixin,
    Vehicle,
    Head,
    GripCategory,
    GripProduct,
    Config,
    Static,
)
from models.pricing import SalaryPosition, SalaryRate, LogisticsRate
from models.system import SqlQueryLog, CalendarSubscription, AppSetting
from models.newsletter import NewsletterSubscriber
from models.mcp import McpApiToken, McpAuditLog
from models.incident import Incident, IncidentToken, IncidentSignedDocument
from models.project_report import ProjectReport
from models.kdrive import KDriveObject
from models.signature_event import SignatureEvent

from models.user_pin import UserPin
