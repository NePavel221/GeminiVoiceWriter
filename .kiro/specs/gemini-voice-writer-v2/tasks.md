# Implementation Plan

- [x] 1. Set up project structure and dependencies


  - Create new directory structure: `services/`, `utils/`, `assets/sounds/`
  - Update `requirements.txt` with new dependencies: `hypothesis`, `sounddevice`, `openai`, `requests`
  - Create `__init__.py` files for all packages
  - _Requirements: 10.1_





- [ ] 2. Implement Utils Layer (ConfigManager, HistoryManager)
  - [x] 2.1 Create ConfigManager class


    - Implement `load()`, `save()`, `get()`, `set()` methods


    - Use `%APPDATA%/GeminiVoiceWriter/` for config storage
    - Handle missing file gracefully with defaults


    - _Requirements: 7.2, 7.3_
  - [ ] 2.2 Write property test for ConfigManager
    - **Property 12: Settings Persistence Round-Trip**
    - **Validates: Requirements 7.2, 7.3**


  - [-] 2.3 Create HistoryManager class with SQLite



    - Implement database schema creation
    - Implement `add()`, `get_page()`, `search()`, `delete()`, `get_total_count()` methods


    - _Requirements: 8.1, 8.2, 8.4, 8.5_
  - [ ] 2.4 Write property tests for HistoryManager
    - **Property 14: History Storage Round-Trip**


    - **Property 15: History Ordering**
    - **Property 16: History Deletion Consistency**

    - **Property 17: History Search Filtering**



    - **Validates: Requirements 8.1, 8.2, 8.4, 8.5**


- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Services Layer (Transcription Providers)
  - [ ] 4.1 Create base TranscriptionProvider abstract class
    - Define `transcribe()`, `validate_api_key()`, `get_models()` abstract methods
    - Create `TranscriptionResult` dataclass
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 4.2 Implement GeminiProvider
    - Use `google-generativeai` SDK
    - Implement transcription with punctuation refinement prompt
    - Calculate cost based on model and duration
    - _Requirements: 5.1, 5.5_
  - [ ] 4.3 Implement OpenRouterProvider
    - Use OpenAI-compatible API endpoints
    - Support multiple models via OpenRouter
    - _Requirements: 5.2, 5.5_
  - [ ] 4.4 Implement OpenAIProvider
    - Use OpenAI Whisper API
    - _Requirements: 5.3, 5.5_
  - [ ] 4.5 Create ProviderFactory
    - Implement `create()` method to instantiate providers by name
    - _Requirements: 5.1, 5.2, 5.3_
  - [x] 4.6 Write property tests for providers

    - **Property 7: Provider Factory Correctness**
    - **Property 9: Error Message Formatting**
    - **Property 13: API Key Validation Format**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.6, 7.5**

- [x] 5. Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.

- [-] 6. Implement Core Layer (AudioRecorder, SoundPlayer)


  - [x] 6.1 Refactor AudioRecorder for async operation

    - Use `sounddevice` for non-blocking recording
    - Implement device enumeration and selection
    - Save as 16kHz mono 16-bit WAV
    - _Requirements: 3.3, 3.4, 3.5_


  - [ ] 6.2 Write property test for AudioRecorder
    - **Property 3: WAV File Format Consistency**

    - **Validates: Requirements 3.4**
  - [x] 6.3 Create SoundPlayer class

    - Implement async sound playback using `sounddevice`
    - Handle missing files gracefully
    - Support enable/disable toggle
    - _Requirements: 9.2, 9.3, 9.4_

  - [x] 6.4 Write property tests for SoundPlayer

    - **Property 18: Sound Playback Non-Blocking**
    - **Property 19: Sound Disabled Behavior**
    - **Validates: Requirements 9.2, 9.3**

  - [x] 6.5 Create placeholder WAV sound files

    - Generate simple beep sounds programmatically or use free assets
    - Place in `assets/sounds/` directory
    - _Requirements: 9.1_


- [ ] 7. Implement Core Layer (HotkeyManager, TextInjector)
  - [x] 7.1 Refactor HotkeyManager for dual modes


    - Implement Toggle Mode (press to start/stop)
    - Implement Hold-to-Record Mode (hold to record, release to stop)
    - Add hotkey validation
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [x] 7.2 Write property tests for HotkeyManager

    - **Property 4: Toggle Mode State Machine**
    - **Property 6: Hotkey Validation**
    - **Validates: Requirements 4.1, 4.3**
  - [x] 7.3 Create TextInjector class


    - Implement keyboard simulation using `pynput`
    - Support configurable typing speed
    - Handle special characters (unicode, newlines)
    - Implement clipboard fallback
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [-] 7.4 Write property tests for TextInjector

    - **Property 10: Clipboard Round-Trip**
    - **Property 11: Special Character Injection**
    - **Validates: Requirements 6.2, 6.5**


- [x] 8. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

- [-] 9. Implement UI Layer (Floating Widget)


  - [x] 9.1 Create FloatingWidget with Gemini theme


    - Implement frameless, always-on-top window
    - Apply Gemini color scheme (#0f0f23 background, #8b5cf6/#3b82f6 accents)
    - Implement drag-to-move functionality
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ] 9.2 Write property test for widget position
    - **Property 1: Widget Position Persistence Round-Trip**
    - **Validates: Requirements 1.3**
  - [ ] 9.3 Implement AnimationOverlay
    - Create pulsing waveform animation for recording state
    - Create spinning loader for processing state
    - Create success checkmark animation
    - Create error indicator animation
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [ ] 9.4 Implement System Tray integration
    - Add tray icon with context menu (Show, Settings, History, Quit)
    - Implement minimize to tray on close
    - Implement restore on double-click
    - _Requirements: 1.4, 1.5, 10.3_

- [ ] 10. Implement UI Layer (Settings and History Windows)
  - [ ] 10.1 Create SettingsWindow with tabs
    - General tab: Provider selection, model selection
    - API Keys tab: Input fields for each provider
    - Hotkeys tab: Hotkey input, mode selection
    - Audio tab: Device selection, sound toggle
    - Output tab: Injection vs clipboard mode, typing speed
    - _Requirements: 7.1, 7.4_
  - [ ] 10.2 Create HistoryWindow
    - Implement list view with pagination
    - Implement search and filter functionality
    - Implement copy-to-clipboard and delete actions
    - _Requirements: 8.2, 8.3, 8.4, 8.5_

- [ ] 11. Wire everything together in main.py
  - [ ] 11.1 Create Application class to orchestrate components
    - Initialize all managers and UI components
    - Connect signals between components
    - Implement recording → transcription → injection flow
    - _Requirements: 3.1, 3.2, 5.4, 6.1_
  - [ ] 11.2 Write property test for async operations
    - **Property 2: Audio Recording Thread Isolation**
    - **Property 8: Async Transcription Non-Blocking**
    - **Validates: Requirements 3.3, 5.4**
  - [ ] 11.3 Implement graceful shutdown
    - Stop all threads on quit
    - Save settings and position
    - Release hotkey registration
    - _Requirements: 10.3, 10.4_

- [ ] 12. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Update packaging configuration
  - [ ] 13.1 Update GeminiVoiceWriter.spec for PyInstaller
    - Include new assets (sounds, icons)
    - Include all new modules
    - _Requirements: 9.1_
