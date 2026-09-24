"""Focused routing tests: provider calls are mocked so no cloud TTS is billed."""
from unittest.mock import AsyncMock
import uuid
import os
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from services import router, gemini, media, generation
from services.tts_defaults import narration_chain, migrate_channel_defaults


@pytest.fixture
def providers(monkeypatch):
    mocks = {name: AsyncMock(return_value=2.5) for name in ('kokoro', 'xtts', 'gtts', 'gemini', 'openai')}
    monkeypatch.setattr(router, '_kokoro', mocks['kokoro'])
    monkeypatch.setattr(router, '_xtts', mocks['xtts'])
    monkeypatch.setattr(media, 'gtts_tts', mocks['gtts'])
    monkeypatch.setattr(gemini, 'tts', mocks['gemini'])
    monkeypatch.setattr(media, 'openai_tts', mocks['openai'])
    monkeypatch.setattr(media, 'humanize_audio', AsyncMock(return_value=2.5))
    monkeypatch.setattr(router, 'available', lambda _: True)
    monkeypatch.setattr(router, '_ok', lambda _: None)
    monkeypatch.setattr(router, '_fail', lambda _: None)
    monkeypatch.setattr(generation, 'record_event', AsyncMock(return_value={'message': 'provider unavailable'}))
    monkeypatch.setenv('GEMINI_API_KEY', 'mock-present-key')
    monkeypatch.setenv('TTS_PROVIDER_ORDER', 'gemini_expr,gemini,openai,kokoro')
    return mocks


@pytest.mark.asyncio
@pytest.mark.parametrize('voice', ['', 'local:auto', 'kokoro:hf_alpha'])
async def test_expressive_local_voice_never_calls_gemini(providers, tmp_path, voice):
    result = await router.tts('नमस्कार', voice, 'hi', tmp_path / 'voice.mp3', expressive=True, direction='dramatic')
    assert result['provider'] == 'kokoro'
    providers['kokoro'].assert_awaited_once()
    providers['gemini'].assert_not_awaited()
    providers['openai'].assert_not_awaited()
    assert router.chain('tts') == ['kokoro', 'xtts', 'gtts']


@pytest.mark.asyncio
async def test_ordered_local_fallback_and_exhaustion(providers, tmp_path):
    order = []
    async def kokoro(*args, **kwargs): order.append('kokoro'); raise RuntimeError('unavailable')
    async def xtts(*args, **kwargs): order.append('xtts'); raise RuntimeError('unavailable')
    async def gtts(*args, **kwargs): order.append('gtts'); return 2.5
    providers['kokoro'].side_effect = kokoro
    providers['xtts'].side_effect = xtts
    providers['gtts'].side_effect = gtts
    result = await router.tts('Hello', 'local:auto', 'en', tmp_path / 'voice.mp3', expressive=True, direction='warm')
    assert order == ['kokoro', 'xtts', 'gtts'] and result['provider'] == 'gtts'
    providers['gtts'].side_effect = RuntimeError('network unavailable')
    with pytest.raises(generation.ProviderFailure, match='Voice generation failed'):
        await router.tts('Hello', 'local:auto', 'en', tmp_path / 'voice.mp3', expressive=True)
    providers['gemini'].assert_not_awaited()
    providers['openai'].assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_gemini_opt_in(providers, tmp_path):
    result = await router.tts('Hello', 'gemini:Charon', 'en', tmp_path / 'voice.wav', expressive=True, direction='warm')
    assert result['provider'] == 'gemini'
    providers['gemini'].assert_awaited_once_with('Hello', 'Charon', tmp_path / 'voice.wav', direction='warm')
    providers['kokoro'].assert_not_awaited()


@pytest.mark.asyncio
async def test_bengali_skips_unsupported_local_models_without_gemini(providers, tmp_path):
    result = await router.tts('নমস্কার', 'local:auto', 'bn', tmp_path / 'voice.mp3', expressive=True)
    assert result['provider'] == 'gtts'
    providers['kokoro'].assert_not_awaited()
    providers['xtts'].assert_not_awaited()
    providers['gemini'].assert_not_awaited()


@pytest.mark.asyncio
async def test_one_time_channel_migration_preserves_later_explicit_choice():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client['tts_policy_test_' + uuid.uuid4().hex]
    try:
        await db.channels.insert_many([
            {'_id': 'old-gemini', 'voice': 'gemini:Charon'}, {'_id': 'old-openai', 'voice': 'onyx'},
            {'_id': 'local', 'voice': 'kokoro:af_bella'}, {'_id': 'missing'},
        ])
        await migrate_channel_defaults(db)
        assert (await db.channels.find_one({'_id': 'old-gemini'}))['voice'] == 'local:auto'
        assert (await db.channels.find_one({'_id': 'old-openai'}))['voice'] == 'local:auto'
        assert (await db.channels.find_one({'_id': 'missing'}))['voice'] == 'local:auto'
        assert (await db.channels.find_one({'_id': 'local'}))['voice'] == 'kokoro:af_bella'
        await db.channels.update_one({'_id': 'old-gemini'}, {'$set': {'voice': 'gemini:Kore'}})
        await migrate_channel_defaults(db)
        assert (await db.channels.find_one({'_id': 'old-gemini'}))['voice'] == 'gemini:Kore'
    finally:
        await client.drop_database(db.name)
        client.close()


def test_new_channel_and_preview_defaults():
    from models import Channel
    from routes import VoicePreviewBody
    from server import CHANNEL_SEEDS
    from services.video_types import VIDEO_TYPES
    assert Channel().voice == VoicePreviewBody().voice == 'local:auto'
    assert all(narration_chain(c['voice'])[0] == 'kokoro' for c in CHANNEL_SEEDS)
    assert all(narration_chain(c['voice'])[0] == 'kokoro' for c in VIDEO_TYPES.values())
    assert narration_chain('xtts:default') == ['xtts', 'gtts']
    assert narration_chain('gtts:default') == ['gtts']