'use strict';
(async()=>{
 const status=document.getElementById('sale-status'),button=document.getElementById('buy');
 try {const r=await fetch('https://votre-zone-de-genie-admin.onrender.com/guide-config',{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();
 if(d.available){document.getElementById('nonce').value=d.nonce;button.disabled=false;status.textContent='Vous serez dirigé vers le paiement sécurisé, puis reviendrez ici pour télécharger votre guide.';}
 else status.textContent='La vente en ligne est en cours de préparation. Aucun paiement ne vous est demandé.';
 }catch{status.textContent='La vente est momentanément indisponible. Réessayez plus tard ou contactez Thierry.';}
 if(new URLSearchParams(location.search).get('paiement')==='annule'){const p=document.createElement('p');p.className='notice';p.textContent='Vous avez quitté le paiement. Vous pouvez reprendre votre achat si vous le souhaitez.';document.querySelector('main').prepend(p);}
 document.querySelector('form').addEventListener('submit',()=>{button.disabled=true;button.textContent='Ouverture du paiement…';});
 window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
})();
