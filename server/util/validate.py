from fastapi import HTTPException

class Validate:
    MAX_FIELD_SIZE = 245  # bytes

    @staticmethod
    def check_field_length(value: str, field_name: str):
        """Validate that a single field does not exceed MAX_FIELD_SIZE bytes."""
        if not isinstance(value, str):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Invalid type for '{field_name}'",
                    "requirements": "Must be a string",
                    "received_type": str(type(value)),
                },
            )

        size = len(value.encode("utf-8"))
        if size > Validate.MAX_FIELD_SIZE:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"'{field_name}' too long",
                    "requirements": f"Must be at most {Validate.MAX_FIELD_SIZE} bytes",
                    "actual_size": size,
                },
            )
