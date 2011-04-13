
drop table if exists font;

create table font(
    font_id integer not null,
    name text not null,
    pygame_name text not null,
    present integer not null,
    ok integer not null,
    
    primary key (font_id)
);


drop table if exists metric;

create table metric(
    metric_id integer not null,
    name text not null,

    primary key (metric_id)
);


drop table if exists charset;

create table charset(
    charset_id integer not null,
    name text not null,
    contents text not null,

    primary key (charset_id)
);


drop table if exists distance_font;

create table distance_font(
    a_font_id integer not null,
    b_font_id integer not null,
    metric_id integer not null,
    charset_id integer not null,
    distance real not null,

    primary key (a_font_id, b_font_id, metric_id, charset_id),
    foreign key (a_font_id) references font (font_id),
    foreign key (b_font_id) references font (font_id),
    foreign key (metric_id) references metric (metric_id),
    foreign key (charset_id) references charset (charset_id)
);


drop table if exists distance_char;

create table distance_char(
    a_font_id integer not null,
    b_font_id integer not null,
    metric_id integer not null,
    thechar text not null,
    distance real not null,

    primary key (a_font_id, b_font_id, metric_id, thechar),
    foreign key (a_font_id) references font (font_id),
    foreign key (b_font_id) references font (font_id),
    foreign key (metric_id) references metric (metric_id)
);


