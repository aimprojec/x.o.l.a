<#
.SYNOPSIS
    Jarvis Native Wake-Word Listener (Zero-Dependency Windows Speech Recognition) 🦋
.DESCRIPTION
    Continuous background wake-word listener using Windows native System.Speech.Recognition.
    Recognizes 'hey jarvis', 'jarvis', 'hey xola', 'xola' with confidence >= 0.65.
    Writes atomic utterance JSON records into the jarvis\ears\ queue for JarvisHarness ingestion.
    Supports -TestEmit for verified offline/CI audio testing.
.PARAMETER EarsDir
    Path to the jarvis\ears\ directory where utterances will be enqueued.
.PARAMETER MinConfidence
    Minimum recognition confidence score required to trigger an utterance (default: 0.65).
.PARAMETER WakeWords
    List of phrases to recognize (default: @("hey jarvis", "jarvis", "hey xola", "xola")).
.PARAMETER TestEmit
    If specified, immediately emits an atomic test utterance JSON and exits.
.PARAMETER TestPhrase
    Phrase used for test emission (default: "hey jarvis").
.PARAMETER Once
    If specified, listen until first valid utterance is captured (or timeout), then exit.
.PARAMETER TimeoutSeconds
    Maximum duration in seconds to listen before exiting (0 = infinite).
#>

[CmdletBinding()]
param(
    [string]$EarsDir = "",
    [double]$MinConfidence = 0.65,
    [string[]]$WakeWords = @("hey jarvis", "jarvis", "hey xola", "xola"),
    [switch]$TestEmit,
    [string]$TestPhrase = "hey jarvis",
    [switch]$Once,
    [int]$TimeoutSeconds = 0,
    [int]$CommandTimeoutSeconds = 8
)

# Enforce UTF-8 encoding
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$WATERMARK = [char]::ConvertFromUtf32(0x1F98B)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $EarsDir) {
    $EarsDir = Join-Path $ScriptDir "ears"
}
if (-not (Test-Path $EarsDir)) {
    New-Item -ItemType Directory -Path $EarsDir -Force | Out-Null
}

function Write-AtomicUtterance {
    param(
        [Parameter(Mandatory=$true)][string]$Phrase,
        [Parameter(Mandatory=$true)][double]$Confidence,
        [Parameter(Mandatory=$true)][string]$TargetDir
    )

    $tsIso = [DateTime]::Now.ToString("yyyy-MM-ddTHH:mm:ss.ffffff")
    $tsSlug = [DateTime]::Now.ToString("yyyyMMdd_HHmmss_ffffff")
    $uid = [Guid]::NewGuid().ToString("N").Substring(0, 8)
    $utteranceId = "ears_${tsSlug}_${uid}"

    $tmpPath = Join-Path $TargetDir "${utteranceId}.tmp"
    $finalPath = Join-Path $TargetDir "${utteranceId}.json"

    $payload = [PSCustomObject]@{
        id         = $utteranceId
        text       = $Phrase
        source     = "mic_command"
        speaker    = "user"
        timestamp  = $tsIso
        processed  = $false
        metadata   = [PSCustomObject]@{
            wake_word  = $Phrase
            confidence = [Math]::Round($Confidence, 4)
        }
        mark       = $WATERMARK
    }

    $jsonStr = $payload | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($tmpPath, $jsonStr, $utf8NoBom)
    Move-Item -Path $tmpPath -Destination $finalPath -Force

    Write-Host "[EARS] $WATERMARK Utterance recorded atomically: $utteranceId -> '$Phrase' (confidence: $([Math]::Round($Confidence, 2)))"
    return [PSCustomObject]@{
        Id = $utteranceId
        FilePath = $finalPath
        Phrase = $Phrase
        Confidence = $Confidence
    }
}

# 1. Test Mode: Emit immediate test utterance and exit
if ($TestEmit) {
    Write-Host "[EARS] $WATERMARK Test mode: emitting test utterance '$TestPhrase'..."
    $result = Write-AtomicUtterance -Phrase $TestPhrase -Confidence 1.0 -TargetDir $EarsDir
    Write-Host "[EARS] $WATERMARK Test utterance emitted successfully: $($result.FilePath)"
    exit 0
}

# 2. Native System.Speech Assembly Loading
try {
    Add-Type -AssemblyName System.Speech
} catch {
    Write-Error "[EARS] $WATERMARK Failed to load System.Speech assembly: $($_.Exception.Message)"
    exit 1
}

# Windows Speech uses local dictation after the wake word. A combined grammar
# also accepts "hey xola check disk space" without a pause.
$engine = $null
try {
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    $choices = New-Object System.Speech.Recognition.Choices
    $choices.Add([string[]]$WakeWords)
    $wakeBuilder = New-Object System.Speech.Recognition.GrammarBuilder
    $wakeBuilder.Culture = $engine.RecognizerInfo.Culture
    $wakeBuilder.Append($choices)
    $wakeGrammar = New-Object System.Speech.Recognition.Grammar($wakeBuilder)
    $wakeGrammar.Name = "WakeOnly"
    $combinedBuilder = New-Object System.Speech.Recognition.GrammarBuilder
    $combinedBuilder.Culture = $engine.RecognizerInfo.Culture
    $combinedBuilder.Append($choices)
    $combinedBuilder.AppendDictation()
    $combinedGrammar = New-Object System.Speech.Recognition.Grammar($combinedBuilder)
    $combinedGrammar.Name = "WakeAndCommand"
    $dictation = New-Object System.Speech.Recognition.DictationGrammar
    $dictation.Name = "CommandDictation"
    $dictation.Enabled = $false
    $engine.LoadGrammar($wakeGrammar)
    $engine.LoadGrammar($combinedGrammar)
    $engine.LoadGrammar($dictation)
    $engine.SetInputToDefaultAudioDevice()
    $engine.BabbleTimeout = [TimeSpan]::FromSeconds(5)
    $startTime = [DateTime]::UtcNow
    Write-Host "[EARS] Say hey xola followed by your request. Ctrl+C stops listening."
    while ($true) {
        if ($TimeoutSeconds -gt 0 -and ([DateTime]::UtcNow - $startTime).TotalSeconds -ge $TimeoutSeconds) { break }
        $heard = $engine.Recognize([TimeSpan]::FromSeconds(2))
        if (-not $heard -or $heard.Confidence -lt $MinConfidence) { continue }
        $command = $heard.Text.Trim()
        foreach ($wake in ($WakeWords | Sort-Object Length -Descending)) {
            if ($command -match ("^(?i)" + [regex]::Escape($wake) + "(?:\s+|$)")) {
                $command = ($command -replace ("^(?i)" + [regex]::Escape($wake) + "\s*"), "").Trim()
                break
            }
        }
        $confidence = $heard.Confidence
        if (-not $command) {
            $wakeGrammar.Enabled = $false
            $combinedGrammar.Enabled = $false
            $dictation.Enabled = $true
            try {
                Write-Host "[EARS] Listening for your command..."
                $followup = $engine.Recognize([TimeSpan]::FromSeconds($CommandTimeoutSeconds))
                if ($followup -and $followup.Confidence -ge $MinConfidence) {
                    $command = $followup.Text.Trim()
                    $confidence = $followup.Confidence
                }
            } finally {
                $dictation.Enabled = $false
                $wakeGrammar.Enabled = $true
                $combinedGrammar.Enabled = $true
            }
        }
        if ($command -and $command -notin @("cancel", "never mind", "nevermind")) {
            Write-AtomicUtterance -Phrase $command -Confidence $confidence -TargetDir $EarsDir | Out-Null
            if ($Once) { break }
        }
    }
} catch {
    Write-Error "[EARS] Speech recognition unavailable: $($_.Exception.Message)"
    exit 1
} finally {
    if ($engine) { $engine.Dispose() }
}
