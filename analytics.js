/* Votre Zone de Génie — mesure d'audience agrégée, sans cookie ni identifiant. */
(function(){
  'use strict';
  if(navigator.doNotTrack==='1'||navigator.globalPrivacyControl===true)return;
  var endpoint='https://votre-zone-de-genie-admin.onrender.com/analytics/event';
  var path=location.pathname;
  var page=path==='/'?'page_home':(path==='/cadeau/'||path==='/cadeau'?'page_cadeau':null);
  function send(event){
    var body='event='+encodeURIComponent(event)+'&path='+encodeURIComponent(path);
    try{
      if(navigator.sendBeacon){
        navigator.sendBeacon(endpoint,new Blob([body],{type:'application/x-www-form-urlencoded'}));
      }else{
        fetch(endpoint,{method:'POST',mode:'cors',keepalive:true,headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body}).catch(function(){});
      }
    }catch(e){}
  }
  if(page)send(page);
  document.addEventListener('click',function(e){
    var a=e.target.closest('a[href]');
    if(!a)return;
    var href=a.getAttribute('href')||'';
    if(href.indexOf('cal.com/')!==-1||href.indexOf('#reservation')!==-1||href.indexOf('#rendez-vous')!==-1)send('click_reserver');
    else if(href.indexOf('/cadeau')!==-1&&page==='page_home')send('click_cadeau');
    else if(href.indexOf('mailto:')===0&&page==='page_cadeau')send('click_interet_cadeau');
  },{passive:true});
})();
