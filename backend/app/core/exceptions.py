"""Custom exception hierarchy â†’ mapped to HTTP responses in main.py."""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AccountError(AppError):
    code = "account_error"
    status_code = 400


class VideoProcessingError(AppError):
    code = "video_processing_error"
    status_code = 422


class InstagramError(AppError):
    code = "instagram_error"
    status_code = 502



class ScheduleError(AppError):
    code = "schedule_error"
    status_code = 400


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class AuthError(AppError):
    code = "auth_error"
    status_code = 401
