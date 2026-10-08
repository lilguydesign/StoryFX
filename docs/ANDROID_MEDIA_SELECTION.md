# Sélection des médias Android

La version 0.4.16 corrige la sélection 0.4.15, qui prenait les premiers résultats
du catalogue trié par date d'ajout. Le choix porte maintenant sur tous les médias
admissibles du dossier exact, avec tirage aléatoire sans remise. Un dossier ambigu,
un quota insuffisant ou un type incompatible reste refusé avant envoi.

L'introduction vidéo dédiée reste en premier. Son URI est exclue du tirage suivant.
Le même média ne peut pas apparaître deux fois dans un lot. Il n'existe pas encore
de mémoire d'exclusion entre plusieurs publications distinctes.

Si plusieurs jours sont connus, le tirage privilégie les jours non encore choisis.
La date de prise de vue valide est prioritaire ; à défaut, la date d'ajout est
utilisée. Cette dernière ne prouve pas le jour de prise de vue. Le fuseau est celui
du téléphone. Les médias sans date deviennent admissibles après représentation
des jours connus, ou immédiatement si zéro ou un seul jour est connu. Le tirage
n'est donc pas uniforme sur tout l'album lorsqu'une diversité de jours est connue.

Android sélectionne les URI directement dans MediaStore. Il ne réalise pas de
scroll aléatoire dans la galerie. Le moteur Windows historique mélangeait les
vignettes visibles et scrollait lorsque nécessaire ; cela ne garantissait pas un
scroll entre chaque image. Ce moteur n'est pas remplacé ou redémarré par cette
correction Android.

Les tests couvrent le quota, les URI distinctes, l'exclusion de l'introduction,
les différents jours de capture malgré une importation groupée, les dates absentes,
le fuseau, l'ambiguïté du dossier et l'accès à la fin du catalogue. Ils ne constituent
pas une validation physique de publication.

La correction de reconnaissance WhatsApp exclut le lecteur de statuts de la liste
des statuts propres. Les diagnostics conservent le maximum d'une seule observation
et leur nombre ; ils ne cumulent pas des éléments possiblement identiques entre
écrans. Les exigences de confirmation restent inchangées. Une tentative incertaine
ne doit pas être rejouée pour vérifier ce correctif.

Facebook natif, grands lots physiquement confirmés, fonctionnement sans USB et
bascule entre Wi-Fi et réseau mobile restent à valider séparément.
