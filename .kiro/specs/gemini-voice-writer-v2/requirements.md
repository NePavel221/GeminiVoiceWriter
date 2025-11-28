# Requirements Document

## Introduction

Полная переработка приложения Gemini Voice Writer — десктопного виджета для голосового ввода текста с использованием AI-транскрипции. Приложение должно обеспечить современный UX в стиле "Whisper Typing", но с брендингом Google Gemini: тёмно-синие фоны, градиенты со звёздами, фиолетово-синие акценты. Ключевые улучшения: асинхронность (UI никогда не зависает), поддержка нескольких AI-провайдеров (Gemini, OpenRouter, OpenAI), история транскрипций, звуковая обратная связь и автоматический ввод текста в активное окно.

## Glossary

- **Floating Widget**: Компактная плавающая панель, всегда поверх других окон, в стиле Apple Dynamic Island
- **Transcription**: Процесс преобразования аудиозаписи в текст с помощью AI-модели
- **Provider**: Сервис AI-транскрипции (Gemini, OpenRouter, OpenAI)
- **Text Injection**: Автоматический ввод текста в активное окно путём симуляции нажатий клавиш
- **Hold-to-Record Mode**: Режим записи, при котором запись идёт пока зажата горячая клавиша
- **Toggle Mode**: Режим записи, при котором первое нажатие начинает запись, второе — останавливает
- **System Tray**: Область уведомлений Windows, где приложение работает в фоне
- **Gemini Theme**: Визуальная тема с Deep Space Blue фоном (#0f0f23), звёздными градиентами и фиолетово-синими акцентами (#8b5cf6, #3b82f6)

## Requirements

### Requirement 1: Floating Widget UI

**User Story:** As a user, I want a sleek floating widget that stays on top of other windows, so that I can quickly access voice recording without switching applications.

#### Acceptance Criteria

1. WHEN the application starts THEN the Floating Widget SHALL display as a compact bar (approximately 300x60 pixels) positioned at the top-center of the screen
2. WHEN the Floating Widget is displayed THEN the system SHALL render it with Gemini Theme colors: Deep Space Blue background (#0f0f23), purple-blue gradient accents (#8b5cf6 to #3b82f6)
3. WHEN the user drags the Floating Widget THEN the system SHALL allow repositioning to any screen location and persist the position across sessions
4. WHEN the user clicks the minimize button THEN the Floating Widget SHALL minimize to the System Tray
5. WHEN the user double-clicks the System Tray icon THEN the Floating Widget SHALL restore to its previous position

### Requirement 2: Recording States and Animations

**User Story:** As a user, I want clear visual feedback during recording and processing, so that I always know the current state of the application.

#### Acceptance Criteria

1. WHEN recording starts THEN the Floating Widget SHALL display a pulsing waveform animation with Gemini sparkle effects in purple-blue colors
2. WHEN recording stops and transcription begins THEN the Floating Widget SHALL display a smooth spinning loader animation
3. WHEN transcription completes successfully THEN the Floating Widget SHALL display a success checkmark with optional statistics (duration, cost) for 3 seconds
4. WHEN an error occurs THEN the Floating Widget SHALL display an error indicator with a brief error message for 5 seconds
5. WHILE the application is idle THEN the Floating Widget SHALL display a subtle breathing animation indicating readiness

### Requirement 3: Audio Recording

**User Story:** As a user, I want non-blocking audio recording with sound feedback, so that I can record without UI freezes and know when recording starts/stops.

#### Acceptance Criteria

1. WHEN recording starts THEN the system SHALL play a subtle "start" sound effect (WAV file, under 500ms duration)
2. WHEN recording stops THEN the system SHALL play a subtle "stop" sound effect (WAV file, under 500ms duration)
3. WHILE recording is active THEN the system SHALL capture audio in a background thread without blocking the UI thread
4. WHEN recording completes THEN the system SHALL save audio as WAV file with 16kHz sample rate, mono channel, 16-bit depth
5. WHEN the selected audio input device is unavailable THEN the system SHALL display an error message and fall back to the default device

### Requirement 4: Global Hotkeys

**User Story:** As a user, I want system-wide hotkeys to control recording, so that I can start/stop recording from any application.

#### Acceptance Criteria

1. WHEN the user presses the configured hotkey in Toggle Mode THEN the system SHALL toggle recording state (start if idle, stop if recording)
2. WHILE the user holds the configured hotkey in Hold-to-Record Mode THEN the system SHALL record audio, and stop when the key is released
3. WHEN the user configures a new hotkey THEN the system SHALL validate the hotkey combination and register it system-wide
4. WHEN a hotkey conflict exists with another application THEN the system SHALL display a warning message to the user
5. WHEN the application starts THEN the system SHALL register the previously saved hotkey configuration

### Requirement 5: Multi-Provider Transcription

**User Story:** As a user, I want to choose between different AI providers (Gemini, OpenRouter, OpenAI), so that I can use my preferred service or switch based on availability.

#### Acceptance Criteria

1. WHEN the user selects Gemini provider THEN the system SHALL use the google-generativeai SDK with the configured API key and model
2. WHEN the user selects OpenRouter provider THEN the system SHALL use OpenAI-compatible API endpoints with the configured API key
3. WHEN the user selects OpenAI provider THEN the system SHALL use the OpenAI Whisper API with the configured API key
4. WHEN transcription is requested THEN the system SHALL execute the API call in a background thread without blocking the UI
5. WHEN the API returns a response THEN the system SHALL apply automatic punctuation and capitalization refinement to the transcribed text
6. WHEN an API error occurs THEN the system SHALL display a user-friendly error message with the error code and suggestion

### Requirement 6: Text Output Handling

**User Story:** As a user, I want the transcribed text to be automatically typed into my active window, so that I can seamlessly continue my work.

#### Acceptance Criteria

1. WHEN transcription completes with Text Injection enabled THEN the system SHALL simulate keyboard input to type the text into the currently active window
2. WHEN transcription completes with clipboard mode enabled THEN the system SHALL copy the text to clipboard and optionally paste it
3. WHEN Text Injection is performed THEN the system SHALL type at a configurable speed (characters per second) to avoid input buffer overflow
4. WHEN the active window does not accept text input THEN the system SHALL fall back to clipboard copy and notify the user
5. WHEN special characters are present in the transcription THEN the system SHALL handle them correctly during Text Injection

### Requirement 7: Settings and Configuration

**User Story:** As a user, I want to configure API keys, hotkeys, and preferences, so that I can customize the application to my needs.

#### Acceptance Criteria

1. WHEN the user opens settings THEN the system SHALL display a modern settings window with tabs for different configuration categories
2. WHEN the user saves settings THEN the system SHALL persist all configuration to a JSON file in the application data directory
3. WHEN the application starts THEN the system SHALL load previously saved settings and apply them
4. WHEN the user changes the audio input device THEN the system SHALL list all available devices and allow selection
5. WHEN the user configures an API key THEN the system SHALL validate the key format and optionally test connectivity

### Requirement 8: Transcription History

**User Story:** As a user, I want to view my past transcriptions, so that I can review, copy, or re-use previous text.

#### Acceptance Criteria

1. WHEN a transcription completes THEN the system SHALL store the record in SQLite database with timestamp, duration, provider, model, cost, and transcribed text
2. WHEN the user opens the history tab THEN the system SHALL display transcriptions in reverse chronological order with pagination (20 items per page)
3. WHEN the user clicks a history item THEN the system SHALL display the full transcription text with copy-to-clipboard option
4. WHEN the user deletes a history item THEN the system SHALL remove it from the database after confirmation
5. WHEN the user searches history THEN the system SHALL filter results by text content, date range, or provider

### Requirement 9: Sound Assets

**User Story:** As a user, I want pleasant audio feedback sounds, so that I have clear non-visual confirmation of recording state changes.

#### Acceptance Criteria

1. WHEN the application is packaged THEN the system SHALL include WAV sound files for start and stop recording events
2. WHEN sound playback is requested THEN the system SHALL play the sound asynchronously without blocking other operations
3. WHEN the user disables sound feedback in settings THEN the system SHALL skip sound playback
4. WHEN a sound file is missing or corrupted THEN the system SHALL log the error and continue operation without crashing

### Requirement 10: Application Lifecycle

**User Story:** As a user, I want the application to run efficiently in the background, so that it's always ready when I need it.

#### Acceptance Criteria

1. WHEN the application starts THEN the system SHALL initialize all components within 3 seconds
2. WHEN the application is minimized to System Tray THEN the system SHALL consume minimal CPU and memory resources (under 50MB RAM when idle)
3. WHEN the user clicks "Quit" from the tray menu THEN the system SHALL gracefully shutdown all threads and release resources
4. WHEN an unhandled exception occurs THEN the system SHALL log the error to a file and display a crash notification without losing unsaved data
