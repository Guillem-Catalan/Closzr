"""
org_people.py — People & Team Membership Data

Auto-generated from the orgchart Supabase table by src/pipelines/orgchart/sync_orgchart.py.
Manual edits will be overwritten on the next orgchart sync.

Contains:
  CRM_OWNER_MAP       — email -> {id, name} for HubSpot owner resolution
  PARTNERS_ORGCHART   — partner team structures (Telefonica, TIM, TELEKOM, Mexico)
  DIRECT_SALES        — direct sales team hierarchy
  XL_SALES            — XL/enterprise sales team
  MANAGER_EMAILS      — set of manager emails
  PERSON_LANG_OVERRIDE — per-person language exceptions
"""

CRM_OWNER_MAP = {
    'abel.exposito@factorial.co': {
        'id': '81684298',
        'name': 'Abel Expósito Roselló',
    },
    'albert.fernandez@factorial.co': {
        'id': '309581666',
        'name': 'Albert Fernandez',
    },
    'alberto.toboso@factorial.co': {
        'id': '86980984',
        'name': 'Alberto Toboso',
    },
    'alejandra.denobregas@factorial.co': {
        'id': '1911202931',
        'name': 'Alejandra De Nóbregas',
    },
    'alejandro.moreno@factorial.co': {
        'id': '34637474',
        'name': 'Alejandro Moreno Luna',
    },
    'alejandro.soto@factorial.co': {
        'id': '32980021',
        'name': 'Alejandro Soto Velasco',
    },
    'alessandro.cardinale@factorial.co': {
        'id': '89052244',
        'name': 'Alessandro Cardinale',
    },
    'alex.martinez@factorial.co': {
        'id': '79352699',
        'name': 'Alex Martinez',
    },
    'alexander.ulrich@factorial.co': {
        'id': '86686795',
        'name': 'Alexander Ulrich',
    },
    'amadeo.cuellar@factorial.co': {
        'id': '82431537',
        'name': 'Amadeo Cuellar',
    },
    'andre.reis@factorial.co': {
        'id': '83619876',
        'name': 'André Reis Pombinho',
    },
    'andrea.alonso@factorial.co': {
        'id': '85923597',
        'name': 'Andrea Alonso de Paz',
    },
    'andrea.castanar@factorial.co': {
        'id': '80330300',
        'name': 'Andrea Castañar Esteban',
    },
    'andrea.galimberti@factorial.co': {
        'id': '343535117',
        'name': 'Andrea Galimberti',
    },
    'andreu.aloguin@factorial.co': {
        'id': '84984317',
        'name': 'Andreu Aloguin Serramia',
    },
    'angel.hernandez@factorial.co': {
        'id': '81867015',
        'name': 'Ángel Hernández',
    },
    'antoni.grau@factorial.co': {
        'id': '33868845',
        'name': 'Antoni Grau Zorita',
    },
    'ariadna.isla@factorial.co': {
        'id': '100419730',
        'name': 'Ariadna Isla Dominguez',
    },
    'arnau.palos@factorial.co': {
        'id': '500008456',
        'name': 'Arnau Palos Figueras',
    },
    'beatriz.bravo@factorial.co': {
        'id': '34637457',
        'name': 'Beatriz Bravo',
    },
    'belen.lombardia@factorial.co': {
        'id': '554650133',
        'name': 'Belén Lombardía',
    },
    'blanca.orti@factorial.co': {
        'id': '343529996',
        'name': 'Blanca Orti Morillo',
    },
    'carlos.acosta@factorial.co': {
        'id': '77159731',
        'name': 'Carlos Acosta',
    },
    'carlos.sanchez@factorial.co': {
        'id': '2078231828',
        'name': 'Carlos Sanchez',
    },
    'carlota.alvarez@factorial.co': {
        'id': '77922017',
        'name': 'Carlota Álvarez',
    },
    'caterina.peraire@factorial.co': {
        'id': '34212948',
        'name': 'Caterina Peraire Lores',
    },
    'cecilia.rinaldo@factorial.co': {
        'id': '32832928',
        'name': 'Cecilia Rinaldo',
    },
    'chiang.nguyen@factorial.co': {
        'id': '32980547',
        'name': 'Chiang Dinh-Khai Nguyen',
    },
    'christian.lombardo@factorial.co': {
        'id': '86980724',
        'name': 'Christian Lombardo',
    },
    'cristian.ramos@factorial.co': {
        'id': '32550211',
        'name': 'Cristian Ramos',
    },
    'cristina.tarres@factorial.co': {
        'id': '85923618',
        'name': 'Cristina Tarrés',
    },
    'daniel.terrasa@factorial.co': {
        'id': '558202936',
        'name': 'Daniel Terrasa',
    },
    'daniela.hernandez@factorial.co': {
        'id': '83250329',
        'name': 'Daniela Hernandez',
    },
    'daniela.orozco@factorial.co': {
        'id': '578909258',
        'name': 'Daniela Orozco Parra',
    },
    'david.clemente@factorial.co': {
        'id': '77408863',
        'name': 'David Clemente',
    },
    'david.donaire@factorial.co': {
        'id': '76655118',
        'name': 'David Donaire',
    },
    'david.soler@factorial.co': {
        'id': '32687506',
        'name': 'David Soler',
    },
    'denis.peramos@factorial.co': {
        'id': '82080024',
        'name': 'Denis Peramos',
    },
    'diana.bernal@factorial.co': {
        'id': '77922801',
        'name': 'Diana Bernal',
    },
    'diego.hernandez@factorial.co': {
        'id': '133287347',
        'name': 'Diego Osvaldo Hernandez Vicuña',
    },
    'edgar.ybarguengoitia@factorial.co': {
        'id': '85521152',
        'name': 'Edgar Ybargüengoitia',
    },
    'edoardo.rapezzi@factorial.co': {
        'id': '86687949',
        'name': 'Edoardo Rapezzi',
    },
    'eduardo.mahr@factorial.co': {
        'id': '554934310',
        'name': 'Eduardo Mahr',
    },
    'eduardo.zafra@factorial.co': {
        'id': '561316186',
        'name': 'Eduardo Zafra',
    },
    'emilio.fabbro@factorial.co': {
        'id': '77408871',
        'name': 'Emilio Fabbro',
    },
    'enrique.gautier@factorial.co': {
        'id': '76126161',
        'name': 'Enrique Gautier Bolz',
    },
    'ernesto.blanco@factorial.co': {
        'id': '80909459',
        'name': 'Ernesto Blanco Sierra',
    },
    'fabiola.villalobos@factorial.co': {
        'id': '94319291',
        'name': 'Fabiola Villalobos Damian',
    },
    'fiona.durr@factorial.co': {
        'id': '82557508',
        'name': 'Fiona Dürr',
    },
    'francesc.terns@factorial.co': {
        'id': '82179188',
        'name': 'Francesc Terns',
    },
    'gabriel.lichtenstein@factorial.co': {
        'id': '32550082',
        'name': 'Gabriel Lichtenstein',
    },
    'gerard.ghneim@factorial.co': {
        'id': '311993943',
        'name': 'Gerard Ghneim Peroy',
    },
    'gerard.tarradas@factorial.co': {
        'id': '1214888545',
        'name': 'Gerard Tarradas Alarcon',
    },
    'giacomo.torresi@factorial.co': {
        'id': '507963188',
        'name': 'Giacomo Torresi',
    },
    'giovanni.laghi@factorial.co': {
        'id': '32147416',
        'name': 'Giovanni Laghi',
    },
    'giuditta.giunta@factorial.co': {
        'id': '77159727',
        'name': 'Giuditta Giunta',
    },
    'gloria.nunez@factorial.co': {
        'id': '81399037',
        'name': 'Gloria Nuñez',
    },
    'guillermo.ferrer@factorial.co': {
        'id': '168739388',
        'name': 'Guillermo Ferrer',
    },
    'gustavo.torres@factorial.co': {
        'id': '188140936',
        'name': 'Gustavo Torres',
    },
    'iban.cordobes@factorial.co': {
        'id': '84370034',
        'name': 'Iban Cordobés',
    },
    'ignacio.catasus@factorial.co': {
        'id': '150984090',
        'name': 'Ignacio Catasús',
    },
    'ignacio.otero@factorial.co': {
        'id': '34450774',
        'name': 'Ignacio Otero',
    },
    'iker.gordo@factorial.co': {
        'id': '77408730',
        'name': 'Iker Gordo',
    },
    'ines.rivera@factorial.co': {
        'id': '78463306',
        'name': 'Inés Rivera',
    },
    'irene.orra@factorial.co': {
        'id': '32980034',
        'name': 'Irene Orra',
    },
    'jacobo.enriquez@factorial.co': {
        'id': '75910515',
        'name': 'Jacobo Enríquez',
    },
    'joan.balana@factorial.co': {
        'id': '124080727',
        'name': 'Joan Balaña',
    },
    'joan.lorenzo@factorial.co': {
        'id': '946496370',
        'name': 'Joan Lorenzo Galles',
    },
    'johanna.henrich@factorial.co': {
        'id': '82431659',
        'name': 'Johanna Henrich',
    },
    'jon.azconobieta@factorial.co': {
        'id': '78463284',
        'name': 'Jon Azconobieta',
    },
    'jonas.tretter@factorial.co': {
        'id': '34213545',
        'name': 'Jonas Tretter',
    },
    'jordi.reina@factorial.co': {
        'id': '83619860',
        'name': 'Jordi Reina Garcia',
    },
    'jose.donis@factorial.co': {
        'id': '554650010',
        'name': 'Jose Donis',
    },
    'josep.fora@factorial.co': {
        'id': '78736698',
        'name': 'Josep Fora',
    },
    'juan.ruiz@factorial.co': {
        'id': '31866070',
        'name': 'Juan Felipe Ruiz',
    },
    'julia.flaque@factorial.co': {
        'id': '32708064',
        'name': 'Júlia Flaqué Porta',
    },
    'karen.andrade@factorial.co': {
        'id': '248927013',
        'name': 'Karen Andrade',
    },
    'katrin.virtbauer@factorial.co': {
        'id': '83903815',
        'name': 'Katrin Virtbauer',
    },
    'l.rodriguez@factorial.co': {
        'id': '684817577',
        'name': 'Luis Rodriguez de Luz',
    },
    'laura.proefrock@factorial.co': {
        'id': '1700853807',
        'name': 'Laura Proefrock',
    },
    'leonhard.zeus@factorial.co': {
        'id': '80791735',
        'name': 'Leonhard Zeus',
    },
    'lorena.tapia@factorial.co': {
        'id': '84016824',
        'name': 'Lorena Tapia Arroyo',
    },
    'lucia.detorres@factorial.co': {
        'id': '32708231',
        'name': 'Lucia De Torres Alcalde',
    },
    'lucia.garana@factorial.co': {
        'id': '33081553',
        'name': 'Lucia Garaña',
    },
    'manuel.conesa@factorial.co': {
        'id': '84984311',
        'name': 'Manuel Conesa',
    },
    'marco.falaschetti@factorial.co': {
        'id': '187721367',
        'name': 'Marco Falaschetti',
    },
    'maria.masoliver@factorial.co': {
        'id': '32147470',
        'name': 'María Masoliver',
    },
    'maria.reina@factorial.co': {
        'id': '1358098012',
        'name': 'Maria Reina Caballero',
    },
    'marta.ruiz@factorial.co': {
        'id': '554655901',
        'name': 'Marta Ruiz Sánchez',
    },
    'maximiliano.velasco@factorial.co': {
        'id': '35659596',
        'name': 'Max Velasco',
    },
    'meritxell.goikoetxea@factorial.co': {
        'id': '35660040',
        'name': 'Meritxell Goikoetxea',
    },
    'miljan.nojkic@factorial.co': {
        'id': '34212992',
        'name': 'Miljan Nojkic',
    },
    'miquel.criado@factorial.co': {
        'id': '32708305',
        'name': 'Miquel Criado',
    },
    'mireia.bach@factorial.co': {
        'id': '103459488',
        'name': 'Mireia Bach Ruiz',
    },
    'nerea.urien@factorial.co': {
        'id': '645417472',
        'name': 'Nerea Urien Meizoso',
    },
    'nicolas.gonzalez@factorial.co': {
        'id': '84394154',
        'name': 'Nicolás González-Tarrío',
    },
    'nil.oleaga@factorial.co': {
        'id': '82847426',
        'name': 'Nil Oleaga',
    },
    'nunzio.fumo@factorial.co': {
        'id': '343525024',
        'name': 'Nunzio Fumo',
    },
    'nuria.delacerda@factorial.co': {
        'id': '80763157',
        'name': 'Nuria De La Cerda Sánchez',
    },
    'nuria.gisbert@factorial.co': {
        'id': '78959985',
        'name': 'Nuria Gisbert Martínez',
    },
    'oriol.gubau@factorial.co': {
        'id': '673801091',
        'name': 'Oriol Gubau',
    },
    'oriol.pesa@factorial.co': {
        'id': '447489166',
        'name': 'Oriol Pesa',
    },
    'pablo.andres@factorial.co': {
        'id': '95103446',
        'name': 'Pablo Andrés Ruiz',
    },
    'paula.gil@factorial.co': {
        'id': '81867010',
        'name': 'Paula Gil',
    },
    'pilar.elizaga@factorial.co': {
        'id': '86980707',
        'name': 'Maria del Pilar Elizaga',
    },
    'pol.bartolome@factorial.co': {
        'id': '105443852',
        'name': 'Pol Bartolomé',
    },
    'roberto.moran@factorial.co': {
        'id': '105445464',
        'name': 'Roberto Morán',
    },
    'ruben.mariscal@factorial.co': {
        'id': '490300827',
        'name': 'Rubén Mariscal',
    },
    'sabri.blaybel@factorial.co': {
        'id': '121160834',
        'name': 'Sabri Blaybel',
    },
    'santiago.tintore@factorial.co': {
        'id': '81399946',
        'name': 'Santiago Tintoré',
    },
    'sebastian.boudet@factorial.co': {
        'id': '84394220',
        'name': 'Sebastian Boudet',
    },
    'sonia.jimenez@factorial.co': {
        'id': '82431538',
        'name': 'Sonia Jimenez Ruiz',
    },
    'stefan.platt@factorial.co': {
        'id': '86980969',
        'name': 'Stefan Platt',
    },
    'tania.diaz@factorial.co': {
        'id': '146400912',
        'name': 'Tania Diaz Soto',
    },
    'tatiana.baltatescu@factorial.co': {
        'id': '33868827',
        'name': 'Tatiana Baltatescu',
    },
    'teresa.santamaria@factorial.co': {
        'id': '390628148',
        'name': 'Teresa Santamaria',
    },
    'xavier.fortuny@factorial.co': {
        'id': '76824216',
        'name': 'Xavier Fortuny',
    },
    'yolanda.tello@factorial.co': {
        'id': '33372303',
        'name': 'Yolanda Tello',
    },
}

PARTNERS_ORGCHART = {
    'Telefonica': {
        'active': False,
        'pipeline_ids': ['11834984', '684767384'],
    },
    'TIM': {
        'active': True,
        'pipeline_ids': ['824790797', '3612610753'],
        'leadership': {
            'tl_pae': {
                'email': 'nunzio.fumo@factorial.co',
                'name': 'Nunzio Fumo',
                'role': 'TL',
            },
            'tl_pbd': {
                'email': 'giacomo.torresi@factorial.co',
                'name': 'Giacomo Torresi',
                'role': 'TL',
            },
            'director': {
                'email': 'andrea.galimberti@factorial.co',
                'name': 'Andrea Galimberti',
                'role': 'Director',
            },
        },
        'pbd': {
            "alessandro.cardinale@factorial.co",
            "cecilia.rinaldo@factorial.co",
            "miljan.nojkic@factorial.co",
        },
        'pae': {
            "christian.lombardo@factorial.co",
            "edoardo.rapezzi@factorial.co",
            "emilio.fabbro@factorial.co",
            "giovanni.laghi@factorial.co",
            "giuditta.giunta@factorial.co",
            "marco.falaschetti@factorial.co",
        },
    },
    'TELEKOM': {
        'active': True,
        'pipeline_ids': ['824790797', '3612610753'],
        'leadership': {
            'tl_pbd': {
                'email': 'fiona.durr@factorial.co',
                'name': 'Fiona Dürr',
                'role': 'TL',
            },
            'tl_pae': {
                'email': 'gabriel.lichtenstein@factorial.co',
                'name': 'Gabriel Lichtenstein',
                'role': 'TL',
            },
            'director': {
                'email': 'laura.proefrock@factorial.co',
                'name': 'Laura Proefrock',
                'role': 'Director',
            },
        },
        'pbd': {
            "alexander.ulrich@factorial.co",
            "chiang.nguyen@factorial.co",
            "johanna.henrich@factorial.co",
        },
        'pae': {
            "enrique.gautier@factorial.co",
            "jonas.tretter@factorial.co",
            "katrin.virtbauer@factorial.co",
            "leonhard.zeus@factorial.co",
            "lior.shechori@factorial.co",
            "stefan.platt@factorial.co",
        },
    },
    'Mexico': {
        'active': True,
        'tl': 'oriol.pesa@factorial.co',
        'tl_name': 'Oriol Pesa',
        'subteams': {
            'Mexico Ernesto': {
                'active': True,
                'tl': 'ernesto.blanco@factorial.co',
                'tl_name': 'Ernesto Blanco Sierra',
                'ae': {"eduardo.mahr@factorial.co", "gustavo.torres@factorial.co"},
            },
            'Mexico Francesc': {
                'active': True,
                'tl': 'francesc.terns@factorial.co',
                'tl_name': 'Francesc Terns',
                'subteams': {
                    'Mexico Meritxell': {
                        'active': True,
                        'tl': 'meritxell.goikoetxea@factorial.co',
                        'tl_name': 'Meritxell Goikoetxea',
                        'ae': {
                            "cristian.ramos@factorial.co",
                            "daniela.orozco@factorial.co",
                            "diana.bernal@factorial.co",
                            "maximiliano.velasco@factorial.co",
                        },
                    },
                },
                'ae': {
                    "diego.hernandez@factorial.co",
                    "fabiola.villalobos@factorial.co",
                    "marta.ruiz@factorial.co",
                },
            },
        },
        'pipeline_ids': ['default', '9048177'],
    },
}

DIRECT_SALES = {
    'pipeline_ids': ['default', '9048177', '831558698'],
    'teams': {
        'DS Joan Balaña': {
            'active': True,
            'tl': 'joan.balana@factorial.co',
            'tl_name': 'Joan Balaña',
            'subteams': {
                'DS Zafra': {
                    'active': True,
                    'tl': 'eduardo.zafra@factorial.co',
                    'tl_name': 'Eduardo Zafra',
                    'ae': {
                        "belen.lombardia@factorial.co",
                        "daniel.terrasa@factorial.co",
                        "yolanda.tello@factorial.co",
                    },
                },
                'DS Monica': {
                    'active': True,
                    'tl': 'monica.ortiz@factorial.co',
                    'tl_name': 'Monica Ortiz',
                    'ae': {
                        "alejandro.soto@factorial.co",
                        "david.clemente@factorial.co",
                        "joane.fuldain@factorial.co",
                        "nerea.urien@factorial.co",
                    },
                },
                'DS Antoni Grau': {
                    'active': True,
                    'tl': 'antoni.grau@factorial.co',
                    'tl_name': 'Antoni Grau Zorita',
                    'subteams': {
                        'DS Mireia': {
                            'active': True,
                            'tl': 'mireia.bach@factorial.co',
                            'tl_name': 'Mireia Bach Ruiz',
                            'subteams': {
                                'DS Rubén': {
                                    'active': True,
                                    'tl': 'ruben.mariscal@factorial.co',
                                    'tl_name': 'Rubén Mariscal',
                                    'ae': {
                                        "andreu.aloguin@factorial.co",
                                        "arnau.palos@factorial.co",
                                        "blanca.orti@factorial.co",
                                        "camila.aldana@factorial.co",
                                        "guillermo.ferrer@factorial.co",
                                        "iban.cordobes@factorial.co",
                                        "miquel.criado@factorial.co",
                                        "nil.oleaga@factorial.co",
                                    },
                                },
                                'DS Andrea C': {
                                    'active': True,
                                    'tl': 'andrea.castanar@factorial.co',
                                    'tl_name': 'Andrea Castañar Esteban',
                                    'ae': {
                                        "abel.exposito@factorial.co",
                                        "alejandro.moreno@factorial.co",
                                        "carlota.alvarez@factorial.co",
                                        "denis.peramos@factorial.co",
                                        "gerard.tarradas@factorial.co",
                                        "nuria.gisbert@factorial.co",
                                        "pablo.andres@factorial.co",
                                        "tatiana.baltatescu@factorial.co",
                                    },
                                },
                            },
                            'ae': {"edgar.ybarguengoitia@factorial.co", "sonia.jimenez@factorial.co"},
                        },
                        'DS Roberto': {
                            'active': True,
                            'tl': 'roberto.moran@factorial.co',
                            'tl_name': 'Roberto Morán',
                            'ae': {
                                "beatriz.bravo@factorial.co",
                                "joan.lorenzo@factorial.co",
                                "jose.donis@factorial.co",
                                "pol.bartolome@factorial.co",
                                "xavier.fortuny@factorial.co",
                            },
                        },
                        'DS Luis': {
                            'active': True,
                            'tl': 'l.rodriguez@factorial.co',
                            'tl_name': 'Luis Rodriguez de Luz',
                            'ae': {
                                "amadeo.cuellar@factorial.co",
                                "daniela.hernandez@factorial.co",
                                "iker.gordo@factorial.co",
                                "irene.orra@factorial.co",
                                "jordi.reina@factorial.co",
                                "maria.reina@factorial.co",
                                "nuria.delacerda@factorial.co",
                            },
                        },
                        'DS Pilar': {
                            'active': True,
                            'tl': 'pilar.elizaga@factorial.co',
                            'tl_name': 'Maria del Pilar Elizaga',
                            'ae': {
                                "alejandra.denobregas@factorial.co",
                                "andrea.alonso@factorial.co",
                                "cristina.tarres@factorial.co",
                                "david.donaire@factorial.co",
                                "julia.flaque@factorial.co",
                                "manuel.conesa@factorial.co",
                            },
                        },
                        'DS Caterina': {
                            'active': True,
                            'tl': 'caterina.peraire@factorial.co',
                            'tl_name': 'Caterina Peraire Lores',
                            'ae': {
                                "alberto.toboso@factorial.co",
                                "ignacio.catasus@factorial.co",
                                "sabri.blaybel@factorial.co",
                                "teresa.santamaria@factorial.co",
                            },
                        },
                    },
                },
            },
        },
    },
}

XL_SALES = {
    'active': True,
    'pipeline_ids': ['685413816', '3576083668'],
    'country_manager': {
        'email': 'ariadna.isla@factorial.co',
        'name': 'Ariadna Isla Dominguez',
    },
    'ae': {
        "andre.reis@factorial.co",
        "ariadna.isla@factorial.co",
        "gerard.ghneim@factorial.co",
        "gloria.nunez@factorial.co",
        "juan.ruiz@factorial.co",
        "lorena.tapia@factorial.co",
    },
    'sdr': {
        "jacobo.enriquez@factorial.co",
        "karen.andrade@factorial.co",
        "oriol.gubau@factorial.co",
        "sebastian.boudet@factorial.co",
    },
}

MANAGER_EMAILS = {
    "albert.fernandez@factorial.co",
    "alex.martinez@factorial.co",
    "domenica.galarza@factorial.co",
    "guillem.catalan@factorial.co",
    "lucas.siroo@factorial.co",
    "marc.macia@factorial.co",
    "marc.sorensen@factorial.co",
    "oriol.delmoral@factorial.co",
    "pau.cruz@factorial.co",
    "samuel.fernandez@factorial.co",
}

PERSON_LANG_OVERRIDE: dict[str, str] = {
    'andre.reis@factorial.co': 'pt',
}
