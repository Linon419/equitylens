from app.models.auth_model import AuthSession, ExternalIdentity
from app.models.user_model import User


def test_google_auth_models_preserve_integer_user_ids() -> None:
    assert User.model_fields["id"].annotation == int | None
    assert ExternalIdentity.model_fields["user_id"].annotation is int
    assert AuthSession.model_fields["user_id"].annotation is int


def test_federated_user_fields_exist() -> None:
    assert User.model_fields["hashed_password"].is_required() is False
    assert User.model_fields["preferred_locale"].default == "en-US"
    assert "avatar_url" in User.model_fields
    assert "created_at" in User.model_fields
    assert "updated_at" in User.model_fields


def test_identity_and_session_constraints_are_named() -> None:
    identity_constraints = {
        constraint.name for constraint in ExternalIdentity.__table__.constraints
    }
    session_indexes = {index.name for index in AuthSession.__table__.indexes}

    assert "uq_external_identity_provider_subject" in identity_constraints
    assert "uq_external_identity_user_provider" in identity_constraints
    assert "ix_auth_session_token_family_id" in session_indexes
