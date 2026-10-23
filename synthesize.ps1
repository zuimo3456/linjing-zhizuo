param([string]$InputPath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskSpeech = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskSpeech.SelectVoice('Microsoft Huihui Desktop')
    $taskSpeech.Rate = 1
    $taskSpeech.SetOutputToWaveFile($OutputPath)
    $taskSpeech.Speak([System.IO.File]::ReadAllText($InputPath, [System.Text.Encoding]::UTF8))
} finally { $taskSpeech.Dispose() }
