'use strict';
(async()=>{const box=document.querySelector('[data-reviews]'),status=document.querySelector('[data-reviews-status]');if(!box)return;try{
 const r=await fetch('https://votre-zone-de-genie-admin.onrender.com/reviews-public',{cache:'no-store'});if(!r.ok)throw Error();const data=await r.json();
 const list=data.reviews||[];if(!list.length){status.textContent='Aucun avis n’a encore été publié. Les retours restent privés tant que leur auteur et Thierry n’en ont pas autorisé la publication.';return;}
 status.textContent='Avis publiés avec l’accord de leur auteur, après relecture par Thierry.';
 const limit=Number(box.dataset.limit)||100;
 for(const review of list.slice(0,limit)){const card=document.createElement('article');card.className='review-card';const quote=document.createElement('blockquote');quote.textContent=review.message;const name=document.createElement('p');name.className='review-author';name.textContent=review.name||'Anonyme';card.append(quote,name);
 if(review.rating){const note=document.createElement('p');note.className='review-date';note.textContent='Appréciation : '+review.rating+'/5';card.append(note);}
 const date=document.createElement('p');date.className='review-date';date.textContent='Déposé le '+new Date(review.submitted_at+'T12:00:00').toLocaleDateString('fr-FR')+' · publié le '+new Date(review.published_at+'T12:00:00').toLocaleDateString('fr-FR');card.append(date);box.append(card);}
 }catch{status.textContent='Les avis ne peuvent pas être affichés pour le moment. Vous pouvez toujours découvrir la démarche ou contacter Thierry.';}})();
