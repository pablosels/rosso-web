# PINs personales para el equipo de barra: uno por persona, con el mismo poder que el PIN de barra
# (puerta de los shows, canje de tarjetas de regalo y Sello ROSSO). Los avisos de la puerta dicen
# quién hizo qué, y se puede dar de baja a alguien sin cambiarle el PIN a nadie más. OJO: dar de baja
# un PIN personal no sirve si esa persona también sabe el PIN GENERAL de barra; cuando todos tengan el
# suyo, conviene rotar el general (ver DESPLEGAR.md) y que sólo lo tenga Pablo.
#
# Pide en una ventana a quién AGREGAR y a quién QUITAR (nombres separados por coma). A cada nombre
# nuevo le inventa un PIN de 8 dígitos. Al final enseña la lista completa EN UNA VENTANA (nunca en
# la terminal) para que se la pases a cada quien, y guarda una copia en api\.pines_barra.json, que
# no va al repo ni a la nube. Lo que usa el API vive en el secreto rosso-pines-barra.
#
#   powershell -ExecutionPolicy Bypass -File "C:\Users\minis\Downloads\rosso-web\api\pines-barra.ps1"

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms

$PROYECTO = 'motor-facturas'
$SERVICIO = 'rosso-web-api'
$REGION   = 'us-central1'
$CUENTA   = 'motor-facturas-job@motor-facturas.iam.gserviceaccount.com'
$SECRETO  = 'rosso-pines-barra'
$LOCAL    = 'C:\Users\minis\Downloads\rosso-web\api\.pines_barra.json'

# PowerShell 5.1 no se detiene cuando un programa externo falla: se revisa a mano cada gcloud
function G {
    $salida = & gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud $($args[0]) $($args[1]) falló" }
    return $salida
}

try {
    # --- 1. lo que ya hay: la copia local o, si no está, el secreto (a una variable, nunca a pantalla)
    $existe = @(G secrets list --project $PROYECTO --format="value(name.basename())") -contains $SECRETO
    $pines = [ordered]@{}
    $base = $null
    if (Test-Path $LOCAL) { $base = Get-Content $LOCAL -Raw -Encoding UTF8 }
    elseif ($existe) { $base = (G secrets versions access latest --secret $SECRETO --project $PROYECTO) -join '' }
    if ($base) {
        $previo = $base | ConvertFrom-Json
        foreach ($p in $previo.PSObject.Properties) { $pines[$p.Name] = [string]$p.Value }
    }
    $actuales = if ($pines.Count) { (@($pines.Keys) -join ', ') } else { '(nadie todavía)' }

    # --- 2. a quién agregar y a quién quitar -------------------------------------------------
    $agregar = [Microsoft.VisualBasic.Interaction]::InputBox(
        "Ya tienen PIN: $actuales`n`n¿A quién le doy PIN nuevo? Nombres separados por coma (vacío = a nadie).`nEjemplo: Ana, Beto",
        "PINes de barra: agregar", "")
    $quitar = [Microsoft.VisualBasic.Interaction]::InputBox(
        "Ya tienen PIN: $actuales`n`n¿A quién le quito el PIN? Nombres separados por coma (vacío = a nadie).",
        "PINes de barra: quitar", "")

    function Nombres($texto) {
        @(($texto -split ',') | ForEach-Object { ($_ -replace '[^\p{L}\p{N} ._-]', '').Trim() } | Where-Object { $_ })
    }
    $nuevos = Nombres $agregar
    $fuera  = Nombres $quitar
    if (-not $nuevos.Count -and -not $fuera.Count) { Write-Host "No cambié nada."; exit 0 }

    foreach ($n in $fuera) {
        $llave = @($pines.Keys) | Where-Object { $_ -ieq $n } | Select-Object -First 1
        if ($llave) { $pines.Remove($llave); Write-Host "   quito a $llave" } else { Write-Host "   $n no tenía PIN" }
    }
    $azar = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    function PinNuevo {
        do {
            $bytes = New-Object byte[] 4
            $azar.GetBytes($bytes)
            $pin = ([BitConverter]::ToUInt32($bytes, 0) % 90000000 + 10000000).ToString()
        } while (@($pines.Values) -contains $pin)
        return $pin
    }
    foreach ($n in $nuevos) {
        $llave = @($pines.Keys) | Where-Object { $_ -ieq $n } | Select-Object -First 1
        if ($llave) { $pines[$llave] = PinNuevo; Write-Host "   PIN nuevo para $llave (el anterior deja de servir)" }
        else { $pines[$n] = PinNuevo; Write-Host "   PIN para $n" }
    }
    $json = if ($pines.Count) { ($pines | ConvertTo-Json -Compress) } else { '{}' }

    # --- 3. la nube primero: secreto y API ---------------------------------------------------
    $tmp = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding $false))
        if ($existe) { G secrets versions add $SECRETO --data-file="$tmp" --project $PROYECTO | Out-Null }
        else {
            G secrets create $SECRETO --data-file="$tmp" --project $PROYECTO | Out-Null
            G secrets add-iam-policy-binding $SECRETO --member="serviceAccount:$CUENTA" `
                --role="roles/secretmanager.secretAccessor" --project $PROYECTO | Out-Null
        }
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Secreto $SECRETO guardado. Actualizando el API (tarda un minuto)..."
    # la primera vez el permiso tarda en propagarse: hasta 3 intentos
    for ($i = 1; $i -le 3; $i++) {
        & gcloud run services update $SERVICIO --region $REGION --project $PROYECTO --update-secrets "PINES_BARRA=${SECRETO}:latest" | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        if ($i -eq 3) { throw "el API no tomó los PINes" }
        Write-Host "   reintento en 20 s..."
        Start-Sleep -Seconds 20
    }
    $trafico = G run services describe $SERVICIO --region $REGION --project $PROYECTO --format="value(status.traffic[0].latestRevision)"
    if ("$trafico" -notmatch 'True') {
        Write-Host "OJO: el tráfico está fijo en una revisión vieja (¿hubo rollback?). Los PINes nuevos no aplican hasta mandar el tráfico a la última:"
        Write-Host "   gcloud run services update-traffic $SERVICIO --region $REGION --project $PROYECTO --to-latest"
    }

    # --- 4. ya en la nube: copia local y la lista, en una ventana ------------------------------
    [IO.File]::WriteAllText($LOCAL, $json, (New-Object System.Text.UTF8Encoding $false))
    $lista = if ($pines.Count) { (@($pines.Keys) | ForEach-Object { "$_ :  $($pines[$_])" }) -join "`n" } else { '(nadie tiene PIN propio)' }
    [System.Windows.Forms.MessageBox]::Show(
        "PINes de barra vigentes:`n`n$lista`n`nPásale a cada quien el suyo en persona. La copia queda en api\.pines_barra.json.",
        "PINes de barra", 'OK', 'Information') | Out-Null
    $pines = $null; $json = $null
    Write-Host "Listo."
} catch {
    Write-Host ""
    Write-Host "No se completó: $($_.Exception.Message)."
    Write-Host "La lista local no cambió. Revisa que gcloud tenga sesión (gcloud auth login) y vuelve a correrlo."
    exit 1
}
