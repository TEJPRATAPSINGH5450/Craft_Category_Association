import numpy as np
import plotly.express as px
import plotly.graph_objects as go

COLORS=['#158f86','#4478bb','#dc9d42','#a164ae']


def style(fig,height=420):
    fig.update_layout(height=height,margin=dict(l=15,r=15,t=35,b=15),font=dict(family='Arial, sans-serif',size=12),
                      colorway=COLORS,legend=dict(orientation='h',y=1.1),hoverlabel=dict(font_size=12))
    return fig


def bar(df,x,y,color=None,orientation='v',height=420):
    fig=px.bar(df,x=x,y=y,color=color,orientation=orientation,color_discrete_sequence=COLORS,
               labels={x:x.replace('_',' ').title(),y:y.replace('_',' ').title()})
    if y=='category': fig.update_yaxes(title=None)
    return style(fig,height)


def scatter_rules(df):
    fig=px.scatter(df,x='support',y='confidence',color='lift',size='invoice_count',size_max=13,
                   hover_data=['antecedent','consequent','leverage'],color_continuous_scale='Teal',render_mode='webgl')
    fig.update_xaxes(tickformat='.0%',title='Support · all invoices in population')
    fig.update_yaxes(tickformat='.0%',title='Confidence')
    return style(fig)


def network(df,limit=15):
    import json
    pairs=df[df.itemset_length.eq(2)].nlargest(limit,['lift','support'])
    nodes=sorted(set(pairs.antecedent)|set(pairs.consequent))
    fig=go.Figure()
    if not nodes: return style(fig)
    pos={n:(np.cos(a),np.sin(a)) for n,a in zip(nodes,np.linspace(0,2*np.pi,len(nodes),endpoint=False))}
    for row in pairs.itertuples():
        x0,y0=pos[row.antecedent]; x1,y1=pos[row.consequent]
        fig.add_trace(go.Scatter(x=[x0,x1],y=[y0,y1],mode='lines',line=dict(width=1+row.support*8,color='#66aaa8'),
             hoverinfo='text',text=f'{row.antecedent} → {row.consequent}<br>Support {row.support:.2%} · confidence {row.confidence:.2%} · lift {row.lift:.2f}',showlegend=False))
        fig.add_annotation(x=x0+.8*(x1-x0),y=y0+.8*(y1-y0),ax=x0+.65*(x1-x0),ay=y0+.65*(y1-y0),xref='x',yref='y',axref='x',ayref='y',
                           text='',showarrow=True,arrowhead=2,arrowwidth=1.3,arrowcolor='#158f86')
    fig.add_trace(go.Scatter(x=[pos[n][0] for n in nodes],y=[pos[n][1] for n in nodes],mode='markers+text',
                  text=[str(i+1) for i in range(len(nodes))],textposition='top center',hovertext=nodes,hoverinfo='text',
                  marker=dict(size=20,color=COLORS[0]),showlegend=False))
    fig.update_xaxes(visible=False,range=[-1.3,1.3]); fig.update_yaxes(visible=False,scaleanchor='x',range=[-1.3,1.3])
    return style(fig,460)

