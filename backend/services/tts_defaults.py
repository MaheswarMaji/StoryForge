"""Local-first narration policy. Cloud TTS requires an explicit voice selection."""
LOCAL_TTS_CHAIN = ('kokoro', 'xtts', 'gtts')
DEFAULT_VOICE = 'local:auto'
MIGRATION_KEY = 'local_tts_defaults_v1'
OPENAI_VOICES = {'alloy', 'ash', 'coral', 'echo', 'fable', 'nova', 'onyx', 'sage', 'shimmer'}


def narration_chain(voice_spec=''):
    voice = (voice_spec or '').strip()
    # Neither an API key, expressive narration nor old TTS_PROVIDER_ORDER values grant consent.
    if voice.startswith('gemini:'):
        return ['gemini', *LOCAL_TTS_CHAIN]
    if voice.startswith('openai:') or voice in OPENAI_VOICES:
        return ['openai', *LOCAL_TTS_CHAIN]
    if voice.startswith('xtts:'):
        return ['xtts', 'gtts']
    if voice.startswith('gtts:'):
        return ['gtts']
    return list(LOCAL_TTS_CHAIN)


async def migrate_channel_defaults(database):
    """One-time conversion; later explicit user choices survive restarts."""
    if await database.settings.find_one({'key': MIGRATION_KEY, 'applied': True}):
        return
    await database.channels.update_many(
        {'voice': {'$not': {'$regex': '^(local:|kokoro:|xtts:|gtts:)'}}},
        {'$set': {'voice': DEFAULT_VOICE}},
    )
    await database.settings.update_one({'key': MIGRATION_KEY}, {'$set': {'applied': True}}, upsert=True)