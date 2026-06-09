import time
import os
import oci
import sys

print("🎯 Connessione ai server Oracle in corso tramite variabili d'ambiente protette...")
try:
    # Generiamo la configurazione leggendola in modo sicuro dai segreti di GitHub
    config = {
        "user": os.environ["OCI_USER"],
        "fingerprint": os.environ["OCI_FINGERPRINT"],
        "key_content": os.environ["OCI_PRIVATE_KEY_CONTENT"],
        "tenancy": os.environ["OCI_TENANCY"],
        "region": os.environ["OCI_REGION"]
    }
    
    compute_client = oci.core.ComputeClient(config)
    network_client = oci.core.VirtualNetworkClient(config)
    identity_client = oci.identity.IdentityClient(config)
    print("✅ Autenticazione riuscita con successo!")
except Exception as e:
    print(f"❌ Errore di autenticazione: {e}")
    sys.exit(1)

COMPARTMENT_ID = config["tenancy"]

# ── LETTURA CHIAVE SSH DA VARIABILE PROTETTA ────────────────────────────────
print("🔑 Caricamento della chiave SSH pubblica...")
SSH_PUBLIC_KEY = os.environ.get("SSH_PUBLIC_KEY")
if not SSH_PUBLIC_KEY:
    print("❌ Errore: la variabile d'ambiente SSH_PUBLIC_KEY è vuota.")
    sys.exit(1)
print("✅ Chiave SSH caricata correttamente!")
# ─────────────────────────────────────────────────────────────────────────────

print("🔍 Rilevamento automatico della zona (Availability Domain)...")
try:
    ads = identity_client.list_availability_domains(compartment_id=COMPARTMENT_ID).data
    if not ads:
        raise Exception("Nessun Availability Domain trovato.")
    AVAILABILITY_DOMAIN = ads[0].name
    print(f"✅ Zona agganciata in automatico: {AVAILABILITY_DOMAIN}")
except Exception as e:
    print(f"❌ Errore nel recupero della zona: {e}")
    sys.exit(1)

print("🔍 Rilevamento automatico della rete (Subnet)...")
try:
    subnets = network_client.list_subnets(compartment_id=COMPARTMENT_ID).data
    if not subnets:
        raise Exception("Nessuna Subnet trouvata.")
    SUBNET_ID = subnets[0].id
    print(f"✅ Subnet agganciata in automatico: {subnets[0].display_name} | CIDR: {subnets[0].cidr_block}")
except Exception as e:
    print(f"❌ Errore nel recupero della rete: {e}")
    sys.exit(1)

print("🔍 Ricerca automatica dell'immagine Oracle Linux per Ampere...")
try:
    images = compute_client.list_images(
        compartment_id=COMPARTMENT_ID,
        shape="VM.Standard.A1.Flex",
        operating_system="Oracle Linux",
        operating_system_version="8"
    ).data
    if not images:
        raise Exception("Nessuna immagine compatibile trovata.")
    IMAGE_ID = images[0].id
    print(f"✅ Immagine Oracle Linux agganciata in automatico!")
except Exception as e:
    print(f"❌ Errore nel recupero dell'immagine: {e}")
    sys.exit(1)

instance_details = oci.core.models.LaunchInstanceDetails(
    availability_domain=AVAILABILITY_DOMAIN,
    compartment_id=COMPARTMENT_ID,
    shape="VM.Standard.A1.Flex",
    shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
        ocpus=4.0,
        memory_in_gbs=24.0
    ),
    source_details=oci.core.models.InstanceSourceViaImageDetails(
        image_id=IMAGE_ID,
        boot_volume_size_in_gbs=100
    ),
    create_vnic_details=oci.core.models.CreateVnicDetails(
        subnet_id=SUBNET_ID,
        assign_public_ip=True
    ),
    metadata={
        "ssh_authorized_keys": SSH_PUBLIC_KEY
    },
    display_name="hermes-agent-ampere"
)

print("\n🚀 AUTOMAZIONE COMPLETA AL 100%! Il cecchino in Cloud entra in azione.")
tentativo = 1

# Impostiamo il limite a 5 ore e mezza per evitare il kill brutale di GitHub
start_time = time.time()
max_duration = 5.5 * 60 * 60  

while True:
    # Controllo del tempo rimasto per questa sessione
    if time.time() - start_time > max_duration:
        print("\n⏳ Limite di sessione raggiunto. Segnalo al workflow di riavviarsi immediatamente...")
        sys.exit(88) # Codice speciale che dice a GitHub di far ripartire il loop

    print(f"\n🚀 [Tentativo {tentativo}] Invio richiesta diretta a Oracle...", end="", flush=True)

    try:
        response = compute_client.launch_instance(instance_details)
        print(f"\n\n🎉 VITTORIA! Server in fase di creazione. ID: {response.data.id}")

        instance_id = response.data.id
        print(f"⏳ Attendo che l'istanza sia RUNNING...")
        while True:
            try:
                instance = compute_client.get_instance(instance_id).data
                state = instance.lifecycle_state
                print(f"   Stato attuale: {state}")
                
                if state == "RUNNING":
                    print(f"\n✅ Server ONLINE e pronto! Il cecchino ha concluso il suo lavoro con successo.")
                    sys.exit(0) # Chiude tutto definitivamente perché abbiamo vinto
                elif state in ("TERMINATED", "TERMINATING", "FAULTY"):
                    print(f"💀 Errore critico: L'istanza è entrata in stato {state}. Uscita.")
                    sys.exit(1)
                    
            except Exception as poll_err:
                print(f"   ⚠️ Errore temporaneo di rete nel polling (riprovo...): {poll_err}")
            
            time.sleep(15)
        break

    except oci.exceptions.ServiceError as e:
        msg = (e.message or "").lower()
        if e.code == "OutOfCapacity" or "capacity" in msg:
            print(" ❌ Risorse esaurite (Out of Capacity).")
            time.sleep(30)
        elif e.code == "TooManyRequests":
            print(" ⚠️ Protezione Oracle attiva (Rate Limit). Attendo 30s...")
            time.sleep(30)
        else:
            print(f"\n⚠️ Risposta imprevista da Oracle [{e.code}]: {e.message}")
            time.sleep(30)

    except Exception as e:
        print(f"\n🚨 Errore imprevisto di esecuzione: {e}")
        time.sleep(30)

    tentativo += 1
