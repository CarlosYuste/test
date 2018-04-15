# -*- coding: utf-8 -*-
from __future__ import unicode_literals

#workflow
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.shortcuts import render, get_object_or_404
from django import forms
from django.http import HttpResponseRedirect

#auth
from django.contrib.auth.decorators import login_required

#tables
from django_tables2 import RequestConfig
from aula.apps.aules.tables2_models import HorariAulaTable, Table2_ReservaAula
from aula.utils.my_paginator import DiggPaginator


#models
from aula.apps.aules.models import Aula, ReservaAula
from aula.apps.horaris.models import FranjaHoraria, Horari
from aula.apps.presencia.models import Impartir
from django.db.models import Q


#forms
from aula.apps.aules.forms import ( disponibilitatAulaPerAulaForm, AulesForm,
                                    reservaAulaForm, disponibilitatAulaPerFranjaForm, )

#helpers
from aula.apps.usuaris.models import User2Professor
from aula.utils.decorators import group_required
from aula.utils import tools
from django.contrib import messages
from django.utils.datetime_safe import datetime


@login_required
@group_required(['professors', 'professional','consergeria'])
def reservaAulaList( request ):
    (user, l4) = tools.getImpersonateUser(request)
    professor = User2Professor( user )     

    reserves = ( ReservaAula
                 .objects
                 .filter( es_reserva_manual = True )
                  )

    table = Table2_ReservaAula( list( reserves) ) 
    table.order_by = ['-dia_reserva','-hora']
    
    RequestConfig(request, paginate={"klass":DiggPaginator , "per_page": 30}).configure(table)
        
    return render(
                  request, 
                  'reservesAules.html', 
                  {'table': table,
                   }
                 )   

# -- wizard per aula 1/3
@login_required
@group_required(['professors', 'professional','consergeria'])
def consultaAulaPerAula(request):
    credentials = tools.getImpersonateUser(request)
    (user, l4) = credentials

    formset = []
    if request.method == 'POST':
        formDisponibilitatAula = disponibilitatAulaPerAulaForm(request.POST)

        if formDisponibilitatAula.is_valid():
            aula = formDisponibilitatAula.cleaned_data['aula']
            data = formDisponibilitatAula.cleaned_data['data']
            year = data.year
            month = data.month
            date = data.day
            next_url = r'/aules/detallAulaReserves/{0}/{1}/{2}/{3}'
            return HttpResponseRedirect(next_url.format(year, month, date, aula.pk))

    else:
        formDisponibilitatAula = disponibilitatAulaPerAulaForm()

    return render(
        request,
        'form.html',
        {'form': formDisponibilitatAula,
         'head': u'Consultar disponibilitat aula',
         'titol_formulari': u"Assistent Reserva d'Aula (1/3)",
         },
    )

# -- wizard per aula 2/3
@login_required
@group_required(['professors', 'professional','consergeria'])
def detallAulaReserves (request, year, month, day, pk):

    credentials = tools.getImpersonateUser(request)
    (user, l4) = credentials

    aula = get_object_or_404(Aula, pk=pk)

    #
    import datetime as t
    try:
        year= int( year)
        month = int( month )
        day = int( day)
    except:
        today = t.date.today()
        year = today.year
        month = today.month
        day = today.day

    data = t.date(year, month, day)

    #
    reserves_dun_dia_un_aula = ( ReservaAula
                                .objects
                                .filter(aula=aula)
                                .filter(dia_reserva=data) )

    #
    franges_del_dia = ( FranjaHoraria
                       .objects
                       .filter( horari__impartir__dia_impartir = data )
                       .order_by('hora_inici')
                      )
    primera_franja = franges_del_dia.first()
    darrera_franja = franges_del_dia.last()

    # -- si l'aula presenta un horari restringit
    q_horari_restringit = Q()
    disponibilitatHoraria = [franja.pk for franja in aula.disponibilitat_horaria.all() ]
    if bool(disponibilitatHoraria):
        franges_reservades = [ reserva.hora.pk for reserva in reserves_dun_dia_un_aula ]
        q_horari_restringit = Q( pk__in = disponibilitatHoraria + franges_reservades )

    #
    franges_reservables = ( FranjaHoraria
                            .objects
                            .filter(hora_inici__gte = primera_franja.hora_inici)
                            .filter(hora_fi__lte = darrera_franja.hora_fi)
                            .filter( q_horari_restringit )
                            ) if primera_franja and darrera_franja else []


    horariAula = []
    for franja in franges_reservables:
        reserva = reserves_dun_dia_un_aula.filter(hora=franja).order_by().first()
        nova_franja = {}
        nova_franja['franja'] = franja
        nova_franja['reserva'] = reserva
        nova_franja['assignatura'] = u", ".join( reserva.impartir_set.values_list( 'horari__assignatura__nom_assignatura', flat=True ).distinct() ) if reserva else u""
        nova_franja['grup'] = u", ".join( reserva.impartir_set.values_list( 'horari__grup__descripcio_grup', flat=True ).distinct() )  if reserva else u""
        nova_franja['professor'] = u", ".join([reserva.usuari.first_name + ' ' + reserva.usuari.last_name]) if reserva else u""
        nova_franja['reservable'] = not bool(reserva) and aula.reservable
        nova_franja['eliminable'] = bool(reserva) and reserva.usuari.pk == user.pk
        
        horariAula.append(nova_franja)

    table = HorariAulaTable(horariAula)
    table.order_by = 'franja'
    RequestConfig(request).configure(table)

    return render(
        request,
        'mostraInfoReservaAula.html',
        {'table': table,
         'aula': aula,
         'dia': data,
         'titol_formulari': u"Assistent Reserva d'Aula (2/3)",
         },
    )

# -- wizard per franja 1/3
@login_required
@group_required(['professors', 'professional','consergeria'])
def consultaAulaPerFranja(request):
    credentials = tools.getImpersonateUser(request)
    (user, l4) = credentials


    if request.method == 'POST':
        formDisponibilitatAula = disponibilitatAulaPerFranjaForm(request.POST)

        if formDisponibilitatAula.is_valid():
            franja = formDisponibilitatAula.cleaned_data['franja']
            data = formDisponibilitatAula.cleaned_data['data']
            year = data.year
            month = data.month
            date = data.day
            next_url = r'/aules/detallFranjaReserves/{0}/{1}/{2}/{3}'
            return HttpResponseRedirect(next_url.format(year, month, date, franja.pk))

    else:
        formDisponibilitatAula = disponibilitatAulaPerFranjaForm()

    for f in formDisponibilitatAula.fields:
        formDisponibilitatAula.fields[f].widget.attrs['class'] = 'form-control ' + formDisponibilitatAula.fields[f].widget.attrs.get('class',"") 
        

    return render(
        request,
        'form.html',
        {'form': formDisponibilitatAula,
         'head': u'Consultar disponibilitat aula per franja',
         'titol_formulari': u"Assistent Reserva d'Aula (1/3)",
         },
    )

# -- wizard per franja 2/3
@login_required
@group_required(['professors', 'professional','consergeria'])
def detallFranjaReserves (request, year, month, day, pk):

    credentials = tools.getImpersonateUser(request)
    (user, l4) = credentials

    franja = get_object_or_404(FranjaHoraria, pk=pk)

    #
    import datetime as t
    try:
        year= int( year)
        month = int( month )
        day = int( day)
    except:
        today = t.date.today()
        year = today.year
        month = today.month
        day = today.day

    data = t.date(year, month, day)

    hi_ha_classe_al_centre_aquella_hora = ( Impartir
                                            .objects
                                            .filter( dia_impartir = data )
                                            .filter( horari__hora = franja )
                                            .exists ()
                                            )
    aules_lliures = Aula.objects.none()
    if hi_ha_classe_al_centre_aquella_hora:
        reservable_aquella_hora = Q(disponibilitat_horaria__isnull = True ) | Q(disponibilitat_horaria = franja )
        reservada = Q( reservaaula__dia_reserva = data )&Q(reservaaula__hora=franja)
        aules_lliures=( Aula
                       .objects
                       .filter( reservable_aquella_hora )
                       .exclude( reservada )
                       .distinct()
                    )

    if request.method == 'POST':
        form = AulesForm(queryset=aules_lliures,
                         data=request.POST, 
                         )

        if form.is_valid():
            next_url = r"/aules/tramitarReservaAula/{0}/{1}/{2}/{3}/{4}/"
            return HttpResponseRedirect(next_url.format( form.cleaned_data['aula'].pk, franja.pk, year, month, day))

    else:
        form = AulesForm(queryset=aules_lliures)

    for f in form.fields:
        form.fields[f].widget.attrs['class'] = 'form-control ' + form.fields[f].widget.attrs.get('class',"") 

    return render(
        request,
        'form.html',
        {'form': form,
         'titol_formulari': u"Assistent Reserva d'Aula (2/3)",
         },
    )


# -- wizard per aula ó franja 3/3
@login_required
@group_required(['professors', 'professional','consergeria'])
def tramitarReservaAula (request, pk_aula, pk_franja , year, month, day):

    credentials = tools.getImpersonateUser(request)
    (user, l4) = credentials

    aula = get_object_or_404(Aula, pk=pk_aula)
    franja = get_object_or_404(FranjaHoraria,pk=pk_franja)

    #
    import datetime as t
    try:
        year= int( year)
        month = int( month )
        day = int( day)
    except:
        today = t.date.today()
        year = today.year
        month = today.month
        day = today.day

    data = t.date(year, month, day)

    #
    novaReserva = ReservaAula(aula=aula,
                              hora=franja,
                              hora_inici=franja.hora_inici,
                              hora_fi=franja.hora_fi,
                              dia_reserva=data,
                              usuari=user,
                              es_reserva_manual=True)
    #
    if request.method=='POST':
        form = reservaAulaForm(request.POST, instance=novaReserva)
        missatge = u"Ho sentim, s'ha detectat un problema amb la reserva"
        if form.is_valid():
            try:
                es_canvi_aula = ( form.cleaned_data['mou_alumnes'] == 'C' )
                if es_canvi_aula:
                    messages.error(request, "Not yet implemented")
                    return HttpResponseRedirect( r'/')
                else:
                    reserva=form.save()
                    missatge = u"Reserva realitzada correctament"
                    messages.info(request, missatge)
                    dia_reserva = reserva.dia_reserva
                    return HttpResponseRedirect(
                        r'/aules/detallAulaReserves/{0}/{1}/{2}/{3}/'.format(dia_reserva.year, dia_reserva.month, 
                                                                             dia_reserva.day, reserva.aula.pk))

            except ValidationError, e:
                for _, v in e.message_dict.items():
                    form._errors.setdefault(NON_FIELD_ERRORS, []).extend(v)

        messages.info(request, missatge)
    else:
        form = reservaAulaForm(instance=novaReserva)

    #
    for f in ['aula','dia_reserva','hora','motiu']:
        form.fields[f].widget.attrs['class'] = 'form-control ' + form.fields[f].widget.attrs.get('class',"") 
        
    #
    return render(
            request,
            'form.html',
            {'form': form,
             'head': u'Reservar aula',
             'titol_formulari': u"Assistent Reserva d'Aula (3/3)",
             },
    )

# -------------------------------------------------------------------------

@login_required
@group_required(['professors', 'professional'])
def eliminarReservaAula (request, pk, pk_aula, year, month, day):

    credentials = tools.getImpersonateUser(request)
    (user, l4) = credentials
    reserva = get_object_or_404(ReservaAula, pk=pk)
    nexturl = r'/aules/detallAulaReserves/{0}/{1}/{2}/{3}/'.format(year, month, day, pk_aula)

    professor = User2Professor(user)
    es_meva = reserva.usuari.pk == professor.pk
    if not l4 and not es_meva:
        messages.error(request, u"No pots anul·lar aquesta reserva, no l'has fet tu.")
        return HttpResponseRedirect(nexturl)

    te_imparticio_associada = reserva.impartir_set.exists()
    if not l4 and te_imparticio_associada:
        messages.error(request, u"No pots anul·lar aquesta reserva, està associada a impartir classe a un grup.")
        return HttpResponseRedirect(nexturl)

    try:
        reserva.delete()
        missatge = u"Reserva anul·lada correctament"
        messages.info(request, missatge)
    except ValidationError, e:
        for _,llista_errors in  e.message_dict.items():
            missatge = u"No s'ha pogut anul·lar la reserva: {0}".format(
                u", ".join( x for x in llista_errors ) 
            ) 
        messages.error(request, missatge)
    
    return HttpResponseRedirect(nexturl)
