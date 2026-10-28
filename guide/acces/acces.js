'use strict';
const endpoint='https://votre-zone-de-genie-admin.onrender.com';
const query=new URLSearchParams(location.hash.slice(1));
const allowed=new URLSearchParams();for(const key of ['order','token','gift'])if(query.has(key))allowed.set(key,query.get(key));
async function verify(){
 const status=document.getElementById('status'),retry=document.getElementById('retry');retry.hidden=true;
 if(!allowed.has('gift')&&!(allowed.has('order')&&allowed.has('token'))){status.textContent='Ouvrez le lien personnel reçu après votre achat ou votre séance.';return;}
 try{const r=await fetch(endpoint+'/guide-access?'+allowed,{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'Vérification indisponible.');
 if(['paid','gift'].includes(d.status)){document.getElementById('title').textContent='Votre guide est prêt.';status.textContent=d.status==='gift'?'Le guide vous est offert. Bonne découverte.':'Votre paiement de 15 € est confirmé. Bonne découverte.';const a=document.getElementById('download');a.href=endpoint+'/guide.pdf?'+allowed;a.hidden=false;document.getElementById('next').hidden=false;if(d.reference)document.getElementById('reference').textContent='Référence : '+d.reference;}
 else {status.textContent=d.status==='pending'?'Votre paiement n’est pas encore confirmé. Réessayez dans quelques instants ; l’accès vous sera aussi envoyé par e-mail après confirmation.':'Cet accès n’est pas actif. Contactez Thierry avec votre référence.';retry.hidden=d.status!=='pending';}
 }catch(e){status.textContent=e.message||'Vérification indisponible. Réessayez sans repayer.';retry.hidden=false;}
}
document.getElementById('retry').addEventListener('click',verify);verify();
