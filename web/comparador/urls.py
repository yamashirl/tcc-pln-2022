from django.urls import path

from . import views

urlpatterns = [
    path('', views.exibir_diarios, name='index'),
    path('diarios', views.exibir_diarios, name='exibir_diarios'),
    path('comparar/<int:paragrafo_id>', views.mostrar_candidatos, name='candidatos'),
    path('comparar/<int:paragrafo_id>/api', views.mostrar_candidatos_api, name='candidatos_api'),
    path('comparar/<int:paragrafo_id>/<int:publicacao_id>', views.comparar, name='comparacao'),
    path('ler/<int:edicao>', views.exibir_do, name='exibir_do'),
    path('informacoes/<int:paragrafo_id>', views.informacoes_paragrafo, name='informacoes_paragrafo'),
    path('buscar/', views.buscar, name='buscar'),
    path('resultado/<str:termo_busca>', views.resultado_busca, name='resultado'),
    path('temp', views.temp, name='temp'),
    path('baixar_do', views.baixar_do_redirect, name='baixar_do_redirect'),
    path('baixar_do/<int:ano>/<int:mes>', views.baixar_do, name='baixar_do'),
]
