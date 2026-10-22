# Guarda las dos llaves de Stripe en la nube y se las da al API del sitio.
#
# Sirve para las tarjetas de regalo y para la venta de boletos: las dos usan
# la misma llave y el mismo webhook.
#
# ANTES de correr esto, en el panel de Stripe (cuenta ROSSO SPEAKEASY, modo real):
#   1. dashboard.stripe.com/apikeys > "Create restricted key".
#      Nombre: rosso-web. Permiso: Checkout Sessions = Write. Todo lo demás: None.
#      Copia la clave que empieza con rk_live_
#   2. dashboard.stripe.com/webhooks > "Add destination".
#      Evento: checkout.session.completed. Formato del payload: Snapshot (NO Thin).
#      URL: https://rosso-web-api-703407013960.us-central1.run.app/stripe/webhook
#      Copia el "Signing secret", que empieza con whsec_
#
# Las llaves se pegan en una ventana, NO en la terminal: así no quedan en el
# historial de PowerShell ni en la pantalla. La ventana puede salir DETRÁS de
# la app de Claude: si no la ves, Alt+Tab.
#
#   powershell -ExecutionPolicy Bypass -File "C:\Users\minis\Downloads\rosso-web\api\stripe-secretos.ps1"

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName Microsoft.VisualBasic

$PROYECTO = 'motor-facturas'
$SERVICIO = 'rosso-web-api'
$REGION   = 'us-central1'
$CUENTA   = 'motor-facturas-job@motor-facturas.iam.gserviceaccount.com'
$S_LLAVE  = 'stripe-key-rosso'
$S_HOOK   = 'stripe-webhook-rosso'

function Guardar-Secreto($nombre, $valor) {
    # sin salto de linea al final: un \n de mas rompe la firma
    $tmp = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($tmp, $valor)
        $existe = & gcloud secrets list --project $PROYECTO --filter="name~^$nombre$" --format="value(name)"
        if ($existe) {
            & gcloud secrets versions add $nombre --data-file="$tmp" --project $PROYECTO | Out-Null
            Write-Host "   ${nombre}: version nueva agregada"
        } else {
            & gcloud secrets create $nombre --data-file="$tmp" --project $PROYECTO | Out-Null
            Write-Host "   ${nombre}: creado"
        }
        & gcloud secrets add-iam-policy-binding $nombre --member="serviceAccount:$CUENTA" `
            --role="roles/secretmanager.secretAccessor" --project $PROYECTO | Out-Null
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
}

# --- 1. la llave restringida -------------------------------------------------
$llave = [Microsoft.VisualBasic.Interaction]::InputBox(
    "Pega la clave restringida de Stripe.`n`n" +
    "Empieza con rk_live_ (la creaste con permiso Checkout Sessions = Escritura).",
    "Stripe: clave restringida", "")
$llave = ($llave -replace '\s', '')
if ($llave.Length -eq 0) { Write-Host "Cancelado, no se cambió nada."; exit 1 }
if ($llave.StartsWith('sk_')) {
    Write-Host "Esa es la clave SECRETA completa (sk_), que puede hacer de todo en tu cuenta."
    Write-Host "No la guardé. Crea una clave RESTRINGIDA (rk_live_) y vuelve a correr esto."
    exit 1
}
if (-not $llave.StartsWith('rk_live_')) {
    Write-Host "Esa no empieza con rk_live_ (¿es de modo prueba?). No cambié nada."
    exit 1
}

# --- 2. probarla ANTES de guardarla --------------------------------------------
# Crea una sesión de pago de $10 que nadie va a pagar y la expira al instante: prueba
# exactamente lo que hace la venta (crear y expirar) con la misma versión de la API.
Write-Host "Probando la clave contra Stripe antes de guardarla (sesión de prueba de `$10, no se cobra)..."
$cab = @{ Authorization = "Bearer $llave"; "Stripe-Version" = "2026-09-30.endive" }
try {
    $prueba = Invoke-RestMethod -Uri 'https://api.stripe.com/v1/checkout/sessions' -Method Post -Headers $cab -Body @{
        "mode" = "payment"
        "allowed_payment_method_types[0]" = "card"
        "success_url" = "https://rossospeakeasy.com/"
        "line_items[0][quantity]" = "1"
        "line_items[0][price_data][currency]" = "mxn"
        "line_items[0][price_data][unit_amount]" = "1000"
        "line_items[0][price_data][product_data][name]" = "Prueba de conexión (no se cobra)"
    }
    Invoke-RestMethod -Uri "https://api.stripe.com/v1/checkout/sessions/$($prueba.id)/expire" -Method Post -Headers $cab | Out-Null
    Write-Host "   la clave crea y expira sesiones de pago: bien"
} catch {
    $codigo = $_.Exception.Response.StatusCode.value__
    if ($codigo -eq 401) { Write-Host "Stripe dice que esa clave no existe o está revocada. No cambié nada." }
    elseif ($codigo -eq 403) { Write-Host "La clave entra pero le falta el permiso Checkout Sessions = Escritura. No cambié nada." }
    else { Write-Host "No pude probar la clave ($codigo): $($_.Exception.Message). No cambié nada." }
    exit 1
}

# --- 3. el secreto del webhook ------------------------------------------------
$hook = [Microsoft.VisualBasic.Interaction]::InputBox(
    "Pega el Secreto de firma del webhook.`n`n" +
    "Empieza con whsec_ (Desarrolladores > Webhooks > tu endpoint > Secreto de firma).",
    "Stripe: secreto del webhook", "")
$hook = ($hook -replace '\s', '')
if ($hook.Length -eq 0) { Write-Host "Cancelado, no se cambió nada."; exit 1 }
if (-not $hook.StartsWith('whsec_')) {
    Write-Host "Ese no empieza con whsec_. No cambié nada."
    exit 1
}

# --- 4. guardarlos en la nube -------------------------------------------------
Write-Host "Guardando en Secret Manager..."
Guardar-Secreto $S_LLAVE $llave
Guardar-Secreto $S_HOOK $hook
$llave = $null; $hook = $null

# --- 5. que el API los recoja -------------------------------------------------
# entre comillas: sin ellas PowerShell parte el valor en la coma
Write-Host "Actualizando el API para que use las llaves..."
& gcloud run services update $SERVICIO --region $REGION --project $PROYECTO `
    --update-secrets "STRIPE_KEY=${S_LLAVE}:latest,STRIPE_WEBHOOK_SECRET=${S_HOOK}:latest" | Out-Null
Write-Host "   $SERVICIO actualizado"

Write-Host ""
Write-Host "Listo. Stripe quedó conectado al sitio."
Write-Host "Avísale a Claude para que lo verifique."
